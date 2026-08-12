"""
User Preferences REST API Endpoints.
Provides GET /preferences and PUT /preferences for UI theme and prompt style customization.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.dependencies import get_current_user_or_guest, get_db
from app.models import User
from app.auth import GuestSession
from app.models import UserPreferences
from app.utils import get_logger

logger = get_logger("finnai.api.preferences")

router = APIRouter(prefix="/preferences", tags=["User Preferences"])


class PreferencesResponse(BaseModel):
    answer_style: str = Field("Detailed", description="Concise | Detailed | Beginner | Expert")
    default_symbols: List[str] = Field(default_factory=lambda: ["RELIANCE", "TCS", "INFY", "HDFCBANK"])
    theme: str = Field("Light", description="Dark | Light | System")


class PreferencesUpdateRequest(BaseModel):
    answer_style: Optional[str] = None
    default_symbols: Optional[List[str]] = None
    theme: Optional[str] = None


@router.get("", response_model=PreferencesResponse, summary="Get user or guest preferences")
def get_preferences(
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
) -> PreferencesResponse:
    """Retrieve UI preferences and default settings."""
    user, guest = auth_identity

    query = db.query(UserPreferences)
    if user:
        pref = query.filter(UserPreferences.user_id == user.id).first()
    elif guest:
        pref = query.filter(UserPreferences.guest_session_id == guest.session_id).first()
    else:
        pref = None

    if not pref:
        return PreferencesResponse()

    return PreferencesResponse(
        answer_style=pref.answer_style,
        default_symbols=pref.default_symbols or ["RELIANCE", "TCS"],
        theme=pref.theme,
    )


@router.put("", response_model=PreferencesResponse, summary="Update user or guest preferences")
def update_preferences(
    body: PreferencesUpdateRequest,
    auth_identity: tuple = Depends(get_current_user_or_guest),
    db: Session = Depends(get_db),
) -> PreferencesResponse:
    """Update UI theme, prompt answer style, and default symbol chips."""
    user, guest = auth_identity

    query = db.query(UserPreferences)
    if user:
        pref = query.filter(UserPreferences.user_id == user.id).first()
    elif guest:
        pref = query.filter(UserPreferences.guest_session_id == guest.session_id).first()
    else:
        pref = None

    if not pref:
        pref = UserPreferences(
            user_id=user.id if user else None,
            guest_session_id=guest.session_id if guest else None,
        )
        db.add(pref)

    if body.answer_style:
        pref.answer_style = body.answer_style.strip()
    if body.default_symbols is not None:
        pref.default_symbols = [s.strip().upper() for s in body.default_symbols if s.strip()]
    if body.theme:
        pref.theme = body.theme.strip()

    db.commit()
    db.refresh(pref)

    return PreferencesResponse(
        answer_style=pref.answer_style,
        default_symbols=pref.default_symbols or ["RELIANCE", "TCS"],
        theme=pref.theme,
    )
