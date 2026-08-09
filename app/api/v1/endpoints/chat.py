"""
Chat & Financial Analysis API Endpoints.
Provides POST /api/v1/chat (JSON completion) and POST /api/v1/chat/stream (SSE token streaming).
Supports chat thread persistence, AI title generation, and 50-message FIFO retention cap enforcement.
"""

import json
import uuid
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import GuestSession
from app.dependencies import get_current_user_or_guest, get_db, get_orchestrator, get_settings
from app.models import ChatMessage, ChatThread
from app.models import User
from app.orchestrator.orchestrator import FinancialOrchestrator
from app.schemas import ChatRequest, ChatResponse
from app.services.factory import get_llm_provider
from app.services.retention_service import RetentionService
from app.utils import get_logger

logger = get_logger("finnai.api.chat")

router = APIRouter(prefix="/chat", tags=["Chat & Analysis"])


class ExtendedChatRequest(ChatRequest):
    """Chat request extending ChatRequest with optional thread ID."""
    chat_id: Optional[str] = Field(default=None, description="Optional existing chat thread ID.")


class EnrichedChatResponse(ChatResponse):
    """Extended response model including thread ID and guest query count metadata."""
    chat_id: str
    queries_remaining: int = -1  # -1 = Unlimited (authenticated user)
    guest_prompt_message: Optional[str] = None


def generate_thread_title(question: str, settings) -> str:
    """Generate a concise AI summary title for a new chat thread using Groq."""
    try:
        provider = get_llm_provider("groq", settings=settings)
        res = provider.generate(
            system_prompt="Summarize the question into a 3-5 word concise thread title. Return title text ONLY. No quotes.",
            user_prompt=question,
            max_tokens=15,
        )
        clean_title = res.content.strip().strip('"\'')
        return clean_title if clean_title else question[:30] + "..."
    except Exception:
        return question[:30] + "..."


@router.post("", response_model=EnrichedChatResponse, summary="Execute financial analysis query")
async def process_chat_query(
    request_body: ExtendedChatRequest,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    orchestrator: FinancialOrchestrator = Depends(get_orchestrator),
    db: Session = Depends(get_db),
    settings = Depends(get_settings),
) -> EnrichedChatResponse:
    """
    Execute multi-agent financial query for authenticated users or guest sessions.
    Persists thread & messages and enforces 50-message FIFO retention cap.
    """
    user, guest = auth_identity
    queries_remaining = -1
    guest_prompt = None

    if guest:
        queries_remaining = guest.queries_remaining
        if not guest.purpose_of_visit:
            guest_prompt = (
                "Welcome Guest! What brings you to FinnAI today? "
                "Submit your purpose of visit (e.g. Retail Investor, Research, Trader, Academic) "
                "via POST /api/v1/auth/guest/purpose."
            )

    # 1. Resolve or Create ChatThread
    chat_id = request_body.chat_id
    if not chat_id:
        chat_id = str(uuid.uuid4())
        title = generate_thread_title(request_body.question, settings)
        thread = ChatThread(
            id=chat_id,
            user_id=user.id if user else None,
            guest_session_id=guest.session_id if guest else None,
            title=title,
        )
        db.add(thread)
        db.commit()
    else:
        thread = db.query(ChatThread).filter(ChatThread.id == chat_id).first()
        if not thread:
            chat_id = str(uuid.uuid4())
            title = generate_thread_title(request_body.question, settings)
            thread = ChatThread(
                id=chat_id,
                user_id=user.id if user else None,
                guest_session_id=guest.session_id if guest else None,
                title=title,
            )
            db.add(thread)
            db.commit()

    # 2. Persist User Prompt Message
    user_msg = ChatMessage(
        thread_id=chat_id,
        role="user",
        content=request_body.question,
    )
    db.add(user_msg)
    db.commit()

    # 3. Load prior conversation history from thread and inject into request
    MAX_HISTORY_TURNS = 8  # Load up to 8 prior messages (4 user + 4 assistant turns)
    try:
        prior_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.thread_id == chat_id)
            .order_by(ChatMessage.id.desc())
            .limit(MAX_HISTORY_TURNS)
            .all()
        )
        # Reverse to chronological order, exclude the just-added user message
        prior_messages = list(reversed(prior_messages))
        # Filter out the message we just inserted (it's the last one)
        prior_messages = [m for m in prior_messages if m.content != request_body.question or m.role != "user" or m.id == prior_messages[-1].id]
        # Build history list (skip the current user message itself)
        history_pairs = [
            {"role": m.role, "content": m.content[:1500]}  # Truncate long messages
            for m in prior_messages
            if not (m.role == "user" and m.content == request_body.question)
        ]
        request_body = request_body.model_copy(update={"chat_history": history_pairs})
    except Exception as e:
        logger.warning(f"Failed to load chat history for thread '{chat_id}': {e}")

    # 4. Delegate to FinancialOrchestrator
    base_response: ChatResponse = await orchestrator.process_query(request_body)

    # 4. Persist Assistant Response Message
    assistant_msg = ChatMessage(
        thread_id=chat_id,
        role="assistant",
        content=base_response.answer,
        images=base_response.images,
        sources=base_response.sources,
        agents_used=base_response.agents_used,
        symbols_queried=base_response.symbols_queried,
        context_truncated=base_response.context_truncated,
    )
    db.add(assistant_msg)
    db.commit()

    # 5. Enforce 50-Message FIFO Retention Cap
    retention_svc = RetentionService(settings)
    retention_svc.enforce_chat_message_limit(
        db=db,
        user_id=user.id if user else None,
        guest_session_id=guest.session_id if guest else None,
    )

    return EnrichedChatResponse(
        chat_id=chat_id,
        answer=base_response.answer,
        sources=base_response.sources,
        agents_used=base_response.agents_used,
        images=base_response.images,
        symbols_queried=base_response.symbols_queried,
        context_truncated=base_response.context_truncated,
        confidence=base_response.confidence,
        timestamp=base_response.timestamp,
        queries_remaining=queries_remaining,
        guest_prompt_message=guest_prompt,
    )


@router.post("/stream", summary="Execute real-time streaming financial analysis query (SSE)")
async def process_chat_query_stream(
    request_body: ExtendedChatRequest,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    orchestrator: FinancialOrchestrator = Depends(get_orchestrator),
) -> StreamingResponse:
    """
    Streams Server-Sent Events (SSE) containing progress events and real-time LLM token chunks.
    """
    user, guest = auth_identity
    logger.info(f"Starting SSE chat stream for {'User:' + user.email if user else 'Guest:' + guest.session_id}")

    async def sse_event_generator():
        event_stream = orchestrator.process_query_event_stream(request_body)
        async for event in event_stream:
            json_data = json.dumps(event)
            yield f"data: {json_data}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")
