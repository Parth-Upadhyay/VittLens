"""
Google OAuth 2.0 & Guest Session API Endpoints.
Provides Google OAuth consent redirect, callback token exchange, /auth/me, and guest purpose onboarding.
"""

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import GuestCookieHandler, GuestSession
from app.auth import create_access_token
from app.config.settings import Settings
from app.dependencies import get_current_user_or_guest, get_db, get_settings
from app.models import User
from app.utils import get_logger

logger = get_logger("finnai.api.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])


class GuestPurposeRequest(BaseModel):
    """Guest Purpose of Visit onboarding request model."""
    purpose_of_visit: str = Field(..., description="Stated purpose of visit (e.g. 'Retail Investor', 'Analyst', 'Trader', 'Academic').")


class UserResponse(BaseModel):
    """User account response model."""
    id: Optional[int] = None
    email: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    provider: str = "guest"
    purpose_of_visit: Optional[str] = None
    queries_used: Optional[int] = None
    queries_remaining: Optional[int] = None


@router.get("/google/login", summary="Redirect to Google OAuth consent screen")
def google_login(settings: Settings = Depends(get_settings)) -> RedirectResponse:
    """
    Redirects user to Google OAuth 2.0 consent authorization screen.
    """
    if not settings.google_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GOOGLE_CLIENT_ID environment variable is not configured.",
        )

    redirect_uri = f"{settings.frontend_url}/api/v1/auth/google/callback"
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }

    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    logger.info("Redirecting to Google OAuth login screen...")
    return RedirectResponse(url=auth_url)


@router.get("/google/callback", summary="Google OAuth callback code exchange")
def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> RedirectResponse:
    """
    Exchanges OAuth code for access token, fetches user info, upserts User in DB, and issues signed JWT bearer token.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth credentials are not fully configured.",
        )

    redirect_uri = f"{settings.frontend_url}/api/v1/auth/google/callback"

    # 1. Exchange code for access token
    token_url = "https://oauth2.googleapis.com/token"
    token_data = urllib.parse.urlencode({
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    try:
        req = urllib.request.Request(token_url, data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_res = json.loads(resp.read().decode("utf-8"))

        google_access_token = token_res.get("access_token")
        if not google_access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve access token from Google.")

        # 2. Fetch user profile
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        req_user = urllib.request.Request(userinfo_url, headers={"Authorization": f"Bearer {google_access_token}"})
        with urllib.request.urlopen(req_user, timeout=10) as resp_user:
            profile = json.loads(resp_user.read().decode("utf-8"))

        email = profile.get("email")
        google_id = profile.get("id")
        name = profile.get("name")
        avatar_url = profile.get("picture")

        if not email or not google_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google user profile missing required fields.")

        # 3. Upsert User in database
        user = db.query(User).filter(User.provider_user_id == google_id).first()
        if not user:
            user = User(
                email=email,
                name=name,
                avatar_url=avatar_url,
                provider="google",
                provider_user_id=google_id,
            )
            db.add(user)
        else:
            user.email = email
            user.name = name
            user.avatar_url = avatar_url

        db.commit()
        db.refresh(user)

        # 4. Issue signed JWT bearer token
        jwt_token = create_access_token(data={"user_id": user.id, "email": user.email})

        # 5. Redirect to frontend with JWT token
        frontend_target = f"{settings.frontend_url}/auth/callback?token={jwt_token}"
        logger.info(f"Google OAuth login succeeded for user '{user.email}'. Redirecting to frontend.")
        return RedirectResponse(url=frontend_target)

    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"OAuth authentication failed: {e}")


@router.get("/me", response_model=UserResponse, summary="Get current user or guest profile")
def get_me(
    auth_identity: tuple = Depends(get_current_user_or_guest),
) -> UserResponse:
    """
    Return profile details for current authenticated User or GuestSession.
    """
    user, guest = auth_identity

    if user:
        return UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            avatar_url=user.avatar_url,
            provider=user.provider,
            purpose_of_visit=user.purpose_of_visit,
        )

    if guest:
        return UserResponse(
            provider="guest",
            purpose_of_visit=guest.purpose_of_visit,
            queries_used=guest.queries_used,
            queries_remaining=guest.queries_remaining,
        )

    return UserResponse(provider="guest", queries_used=0, queries_remaining=3)


@router.post("/guest/purpose", summary="Submit guest purpose of visit")
def submit_guest_purpose(
    body: GuestPurposeRequest,
    request: Request,
    response: Response,
) -> Dict[str, Any]:
    """
    Stores guest purpose of visit in signed guest_session cookie.
    """
    handler = GuestCookieHandler()
    cookie_val = request.cookies.get("guest_session")
    session = handler.parse_cookie_payload(cookie_val) if cookie_val else None

    if session is None:
        session = GuestSession()

    session.purpose_of_visit = body.purpose_of_visit.strip()
    signed_val = handler.sign_cookie_payload(session)

    response.set_cookie(
        key="guest_session",
        value=signed_val,
        max_age=60 * 60 * 24 * 30,
        httponly=True,
        samesite="lax",
    )

    logger.info(f"Updated guest session '{session.session_id}' purpose of visit: '{session.purpose_of_visit}'")
    return {
        "status": "success",
        "message": f"Welcome! Thank you for sharing your purpose of visit: '{session.purpose_of_visit}'.",
        "session_id": session.session_id,
        "purpose_of_visit": session.purpose_of_visit,
    }
