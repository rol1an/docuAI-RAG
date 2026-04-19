"""Direct RAG Pipeline.

Retrieve → Build Context → Stream LLM response → Parse Triad Structure.
No agent loop — deterministic and predictable.
"""

from __future__ import annotations

import logging
import re
from collections.abc import AsyncGenerator
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.rag.models import SearchResult
from app.rag.retrieval import RetrievalService

logger = logging.getLogger(__name__)

_RAG_SYSTEM_PROMPT = """\
你是一个专业的文档问答助手，根据提供的文档片段回答问题。

请严格按照以下三联格式输出，不得省略任何区块：

【结论】
用1-3句话直接给出核心结论。

【证据】
从原文中精确引用支撑结论的句子，每条引用单独一行，格式为：
> "原文引用内容" — [编号] 文件名, p.页码

【来源】
列出引用的来源，格式为：
[编号] 文件名, p.页码

规则：
- 所有引用必须来自下方提供的文档片段，不得虚构
- 编号 [1][2] 等对应文档片段的序号
- 若信息不足，在【结论】区块中说明，【证据】区块写"（文档中未找到直接证据）"
- 不要在三联结构之外添加额外文字\
"""

_RAG_USER_TEMPLATE = """\
文档片段：
{context}

问题：{question}\
"""


class RAGPipeline:
    """Retrieve → Stream → Parse Triad pipeline.

    Usage:
        pipeline = RAGPipeline(retrieval_service)
        async for event in pipeline.stream(query, history, collection):
            # event is one of:
            # {"type": "retrieval_start"}
            # {"type": "citations", "citations": [...]}
            # {"type": "token", "content": "..."}
            # {"type": "done", "full_text": "..."}
            # {"type": "answer_structured", "structured": {...}}
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
            page_info = f", p.{page}" if page else ""
            parts.append(f"[{i}] {filename}{page_info}\n{r.content}")
        return "\n\n---\n\n".join(parts)

    def _build_citations(self, results: list[SearchResult]) -> list[dict[str, Any]]:
        citations = []
        seen_content: set[str] = set()
        for r in results:
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
                    "confidence": round(r.score, 4),
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
            HumanMessage(content=_RAG_USER_TEMPLATE.format(context=context, question=question))
        )
        return messages

    @staticmethod
    def _parse_triad(text: str) -> dict[str, Any]:
        """Parse triad structure from model output.

        Expected format:
            【结论】
            ...conclusion...

            【证据】
            > "quote" — [N] filename, p.X

            【来源】
            [N] filename, p.X

        Returns a dict with parse_success=True on success, False on fallback.
        """
        conclusion_match = re.search(r"【结论】\s*(.*?)(?=【|$)", text, re.DOTALL)
        evidence_match = re.search(r"【证据】\s*(.*?)(?=【|$)", text, re.DOTALL)

        if not conclusion_match or not evidence_match:
            return {"parse_success": False, "conclusion": "", "evidence": []}

        conclusion = conclusion_match.group(1).strip()
        evidence_text = evidence_match.group(1).strip()

        evidence_items = []
        for line in evidence_text.splitlines():
            line = line.strip()
            # Match: > "quote" — [N] ...  or  > "quote" - [N] ...
            quote_match = re.match(r'^>\s*["""](.+?)["""]\s*[—\-–]\s*\[(\d+)\]', line)
            if quote_match:
                evidence_items.append(
                    {
                        "quote": quote_match.group(1).strip(),
                        "citation_index": int(quote_match.group(2)) - 1,  # 0-based
                    }
                )

        if not conclusion:
            return {"parse_success": False, "conclusion": "", "evidence": []}

        return {
            "parse_success": True,
            "conclusion": conclusion,
            "evidence": evidence_items,
        }

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
        5. {"type": "answer_structured", "structured": AnswerStructured}
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
            no_doc_msg = "未在已上传的文档中找到相关信息，请确认相关文档已上传。"
            yield {"type": "token", "content": no_doc_msg}
            yield {"type": "done", "full_text": no_doc_msg}
            yield {
                "type": "answer_structured",
                "structured": {"parse_success": False, "conclusion": no_doc_msg, "evidence": []},
            }
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
            error_msg = f"\n\n[生成回答时出错：{exc}]"
            full_text += error_msg
            yield {"type": "token", "content": error_msg}

        yield {"type": "done", "full_text": full_text}

        # ── Step 4: Parse triad structure ─────────────────────────────
        structured = self._parse_triad(full_text)
        logger.info(
            f"[RAGPipeline] Triad parse: success={structured['parse_success']}, "
            f"evidence_count={len(structured.get('evidence', []))}"
        )
        yield {"type": "answer_structured", "structured": structured}
