"""Direct RAG Pipeline.

Retrieve → Build Context → Stream LLM response.
No agent loop — deterministic and predictable.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.rag.models import SearchResult
from app.rag.retrieval import RetrievalService

logger = logging.getLogger(__name__)

_RAG_SYSTEM_PROMPT = """\
You are a helpful assistant that answers questions based on the provided document context.

- Base your answer on the context below. Cite sources using [1], [2], etc. inline.
- If the context is insufficient, say what you can and note the gap clearly.
- At the end of your response, list cited sources:
  Sources:
  [1] filename.pdf, page 3
- Never fabricate citations or invent information not in the context.\
"""

_RAG_USER_TEMPLATE = """\
Context from documents:
{context}

Question: {question}\
"""


class RAGPipeline:
    """Retrieve → Stream pipeline.

    Usage:
        pipeline = RAGPipeline(retrieval_service)
        async for event in pipeline.stream(query, history, collection):
            # event is one of:
            # {"type": "retrieval_start"}
            # {"type": "citations", "citations": [...]}
            # {"type": "token", "content": "..."}
            # {"type": "done", "full_text": "..."}
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        model_name: str | None = None,
        collection: str | None = None,
    ) -> None:
        self.retrieval = retrieval_service
        self.model_name = model_name or settings.AI_MODEL
        self.default_collection = collection or settings.rag.collection_name

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(self, results: list[SearchResult]) -> str:
        parts = []
        for i, r in enumerate(results, 1):
            filename = r.metadata.get("filename", "unknown")
            page = r.metadata.get("page_num", "")
            page_info = f", page {page}" if page else ""
            parts.append(f"[{i}] Source: {filename}{page_info}\n{r.content}")
        return "\n\n---\n\n".join(parts)

    def _build_citations(self, results: list[SearchResult]) -> list[dict[str, Any]]:
        citations = []
        seen_content: set[str] = set()
        for r in results:
            # Deduplicate by first 120 chars — catches identical chunks from multiple ingestions
            content_key = r.content[:120].strip()
            if content_key in seen_content:
                continue
            seen_content.add(content_key)
            meta = r.metadata
            citations.append(
                {
                    "doc_id": r.parent_doc_id or "",
                    "filename": meta.get("filename", "unknown"),
                    "page_number": meta.get("page_num") or None,
                    "text_snippet": r.content[:200],
                    "score": round(r.score, 4),
                }
            )
        return citations

    def _build_messages(
        self,
        question: str,
        context: str,
        history: list[dict[str, str]] | None,
    ) -> list[HumanMessage | AIMessage | SystemMessage]:
        messages: list[HumanMessage | AIMessage | SystemMessage] = [
            SystemMessage(content=_RAG_SYSTEM_PROMPT)
        ]
        for msg in history or []:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
        messages.append(
            HumanMessage(
                content=_RAG_USER_TEMPLATE.format(context=context, question=question)
            )
        )
        return messages

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def stream(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
        collection: str | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream a RAG response for the given query.

        Yields events in order:
        1. {"type": "retrieval_start"}
        2. {"type": "citations", "citations": list[Citation]}
        3. {"type": "token", "content": str}  (one per LLM chunk)
        4. {"type": "done", "full_text": str}
        """
        target_collection = collection or self.default_collection

        # ── Step 1: Retrieve ──────────────────────────────────────────
        yield {"type": "retrieval_start"}

        try:
            results = await self.retrieval.retrieve(
                query=query,
                collection_name=target_collection,
                limit=5,
                use_reranker=True,
            )
        except Exception as exc:
            logger.error(f"[RAGPipeline] Retrieval failed: {exc}")
            results = []

        citations = self._build_citations(results)
        yield {"type": "citations", "citations": citations}

        if not results:
            no_doc_msg = (
                "I couldn't find relevant information in the uploaded documents. "
                "Please make sure the relevant documents have been uploaded."
            )
            yield {"type": "token", "content": no_doc_msg}
            yield {"type": "done", "full_text": no_doc_msg}
            return

        # ── Step 2: Build context + prompt ────────────────────────────
        context = self._build_context(results)
        messages = self._build_messages(query, context, history)

        # ── Step 3: Stream LLM ────────────────────────────────────────
        llm = ChatOpenAI(
            model=self.model_name,
            temperature=0.1,
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL or None,
            streaming=True,
        )

        full_text = ""
        try:
            async for chunk in llm.astream(messages):
                token = chunk.content if hasattr(chunk, "content") else str(chunk)
                if token:
                    full_text += token
                    yield {"type": "token", "content": token}
        except Exception as exc:
            logger.error(f"[RAGPipeline] LLM streaming error: {exc}")
            error_msg = f"\n\n[Error generating response: {exc}]"
            full_text += error_msg
            yield {"type": "token", "content": error_msg}

        yield {"type": "done", "full_text": full_text}
