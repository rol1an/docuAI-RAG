"""AI Agent WebSocket routes — direct RAG pipeline with streaming."""

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app.api.deps import get_conversation_service, get_current_user_ws
from app.db.models.user import User
from app.db.session import get_db_context
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    MessageCreate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_rag_pipeline(model_name: str | None = None) -> Any:
    """Create a RAGPipeline instance with all dependencies."""
    from app.core.config import settings
    from app.rag.embeddings import EmbeddingService
    from app.rag.pipeline import RAGPipeline
    from app.rag.reranker import RerankService
    from app.rag.retrieval import RetrievalService
    from app.rag.vectorstore import PgVectorStore

    embedder = EmbeddingService(settings=settings.rag)
    vector_store = PgVectorStore(settings=settings.rag, embedding_service=embedder)
    reranker = RerankService(settings=settings.rag)
    retrieval = RetrievalService(
        vector_store=vector_store,
        settings=settings.rag,
        rerank_service=reranker,
    )
    return RAGPipeline(retrieval_service=retrieval, model_name=model_name)


@router.get("/agent/models")
async def list_models() -> dict[str, Any]:
    """Return available LLM models and the current default."""
    from app.core.config import settings

    return {
        "default": settings.AI_MODEL,
        "models": settings.AI_AVAILABLE_MODELS,
    }


class AgentConnectionManager:
    """WebSocket connection manager for AI agent."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Agent WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(
            f"Agent WebSocket disconnected. Total connections: {len(self.active_connections)}"
        )

    async def send_event(self, websocket: WebSocket, event_type: str, data: Any) -> bool:
        """Send a JSON event to a specific WebSocket client.

        Returns True if sent successfully, False if connection is closed.
        """
        try:
            await websocket.send_json({"type": event_type, "data": data})
            return True
        except (WebSocketDisconnect, RuntimeError):
            # Connection already closed
            return False


manager = AgentConnectionManager()



@router.websocket("/ws/agent")
async def agent_websocket(
    websocket: WebSocket,
    user: User = Depends(get_current_user_ws),
) -> None:
    """WebSocket endpoint for AI agent with streaming support.

    Uses LangChain stream() to stream agent events including:
    - user_prompt: When user input is received
    - text_delta: Streaming text from the model
    - tool_call: When a tool is called
    - tool_result: When a tool returns a result
    - final_result: When the final result is ready
    - complete: When processing is complete
    - error: When an error occurs

    Expected input message format:
    {
        "message": "user message here",
        "history": [{"role": "user|assistant|system", "content": "..."}],
        "conversation_id": "optional-uuid-to-continue-existing-conversation"
    }

    Authentication: Requires a valid JWT token passed as a query parameter or header.

    Persistence: Set 'conversation_id' to continue an existing conversation.
    If not provided, a new conversation is created. The conversation_id is
    returned in the 'conversation_created' event.
    """

    await manager.connect(websocket)

    # Conversation state per connection
    conversation_history: list[dict[str, str]] = []
    current_conversation_id: str | None = None

    try:
        while True:
            # Receive user message
            data = await websocket.receive_json()
            user_message = data.get("message", "")
            file_ids = data.get("file_ids", [])

            if not user_message and not file_ids:
                await manager.send_event(websocket, "error", {"message": "Empty message"})
                continue

            # Handle conversation persistence
            try:
                async with get_db_context() as db:
                    conv_service = get_conversation_service(db)

                    # Get or create conversation
                    requested_conv_id = data.get("conversation_id")
                    if requested_conv_id:
                        current_conversation_id = requested_conv_id
                        # Verify conversation exists and update title if empty
                        conv = await conv_service.get_conversation(UUID(requested_conv_id))
                        if not conv.title and user_message:
                            title = user_message[:50] if len(user_message) > 50 else user_message
                            await conv_service.update_conversation(
                                UUID(requested_conv_id), ConversationUpdate(title=title)
                            )
                    elif not current_conversation_id:
                        # Create new conversation
                        conv_data = ConversationCreate(
                            user_id=user.id,
                            title=user_message[:50] if len(user_message) > 50 else user_message,
                        )
                        conversation = await conv_service.create_conversation(conv_data)
                        current_conversation_id = str(conversation.id)
                        await manager.send_event(
                            websocket,
                            "conversation_created",
                            {"conversation_id": current_conversation_id},
                        )

                    # Save user message
                    user_msg = await conv_service.add_message(
                        UUID(current_conversation_id),
                        MessageCreate(role="user", content=user_message),
                    )
                    # Link uploaded files to this message
                    if file_ids:
                        try:
                            await conv_service.link_files_to_message(user_msg.id, file_ids)
                        except Exception as e:
                            logger.warning(f"Failed to link files: {e}")
            except Exception as e:
                logger.warning(f"Failed to persist conversation: {e}")
                # Continue without persistence

            await manager.send_event(websocket, "user_prompt", {"content": user_message})

            try:
                selected_model = data.get("model")
                collection = data.get("collection")  # optional: client may specify collection
                pipeline = _get_rag_pipeline(model_name=selected_model)

                final_output = ""
                await manager.send_event(websocket, "model_request_start", {})

                async for event in pipeline.stream(
                    query=user_message,
                    history=conversation_history,
                    collection=collection,
                ):
                    etype = event["type"]

                    if etype == "citations":
                        await manager.send_event(websocket, "citations", {"citations": event["citations"]})

                    elif etype == "token":
                        await manager.send_event(websocket, "text_delta", {"content": event["content"]})
                        final_output += event["content"]

                    elif etype == "done":
                        final_output = event.get("full_text", final_output)

                await manager.send_event(websocket, "final_result", {"output": final_output})

                # Update in-memory conversation history
                conversation_history.append({"role": "user", "content": user_message})
                if final_output:
                    conversation_history.append({"role": "assistant", "content": final_output})

                # Persist assistant response
                if current_conversation_id and final_output:
                    try:
                        async with get_db_context() as db:
                            conv_service = get_conversation_service(db)
                            await conv_service.add_message(
                                UUID(current_conversation_id),
                                MessageCreate(
                                    role="assistant",
                                    content=final_output,
                                    model_name=pipeline.model_name,
                                ),
                            )
                    except Exception as e:
                        logger.warning(f"Failed to persist assistant response: {e}")

                await manager.send_event(websocket, "complete", {"conversation_id": current_conversation_id})

            except WebSocketDisconnect:
                logger.info("Client disconnected during RAG pipeline processing")
                break
            except Exception as e:
                logger.exception(f"Error processing RAG request: {e}")
                await manager.send_event(websocket, "error", {"message": str(e)})

    except WebSocketDisconnect:
        pass  # Normal disconnect
    finally:
        manager.disconnect(websocket)
