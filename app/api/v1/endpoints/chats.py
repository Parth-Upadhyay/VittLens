"""
Chat Thread History Management Endpoints.
Provides GET /chats, GET /chats/{id}, and DELETE /chats/{id}.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user_or_guest, get_db
from app.models import ChatMessage, ChatThread
from app.models import User
from app.auth import GuestSession
from app.utils import get_logger

logger = get_logger("finnai.api.chats")

router = APIRouter(prefix="/chats", tags=["Chat History"])


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    images: List[str] = Field(default_factory=list)
    sources: List[str] = Field(default_factory=list)
    agents_used: List[str] = Field(default_factory=list)
    symbols_queried: List[str] = Field(default_factory=list)
    context_truncated: bool = False
    created_at: str


class ChatThreadResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


@router.get("", response_model=List[ChatThreadResponse], summary="List user chat threads")
def list_chat_threads(
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
) -> List[ChatThreadResponse]:
    """List all active chat threads for current authenticated user or guest session."""
    user, guest = auth_identity

    query = db.query(ChatThread)
    if user:
        query = query.filter(ChatThread.user_id == user.id)
    elif guest:
        query = query.filter(ChatThread.guest_session_id == guest.session_id)
    else:
        return []

    threads = query.order_by(ChatThread.updated_at.desc()).all()
    results = []
    for t in threads:
        results.append(
            ChatThreadResponse(
                id=t.id,
                title=t.title,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
                message_count=len(t.messages),
            )
        )

    return results


@router.get("/{chat_id}", response_model=List[ChatMessageResponse], summary="Get messages in a thread")
def get_thread_messages(
    chat_id: str,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
) -> List[ChatMessageResponse]:
    """Retrieve message history for a specific chat thread."""
    user, guest = auth_identity

    thread = db.query(ChatThread).filter(ChatThread.id == chat_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found.")

    if user and thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
    if guest and thread.guest_session_id != guest.session_id and not thread.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return [
        ChatMessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            images=m.images or [],
            sources=m.sources or [],
            agents_used=m.agents_used or [],
            symbols_queried=m.symbols_queried or [],
            context_truncated=bool(m.context_truncated),
            created_at=m.created_at.isoformat(),
        )
        for m in thread.messages
    ]


@router.delete("/{chat_id}", summary="Delete a chat thread")
def delete_chat_thread(
    chat_id: str,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a chat thread and cascade delete all its messages."""
    user, guest = auth_identity

    thread = db.query(ChatThread).filter(ChatThread.id == chat_id).first()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat thread not found.")

    if user and thread.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    db.delete(thread)
    db.commit()
    logger.info(f"Deleted chat thread '{chat_id}'")
    return {"status": "success", "message": f"Chat thread '{chat_id}' deleted successfully."}
