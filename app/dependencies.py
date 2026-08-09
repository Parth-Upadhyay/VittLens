"""
Dependency Injection container for FinnAI Platform FastAPI endpoints.
Provides get_db(), get_current_user_or_guest(), and get_orchestrator().
"""

from typing import Generator, Optional, Tuple, Union
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import GuestCookieHandler, GuestSession, get_guest_session
from app.auth import decode_access_token
from app.config.settings import Settings
from app.db.database import SessionLocal
from app.models import User
from app.orchestrator.orchestrator import FinancialOrchestrator
from app.utils import get_logger

logger = get_logger("finnai.dependencies")

security = HTTPBearer(auto_error=False)

# Singleton Orchestrator instance
_orchestrator_instance: Optional[FinancialOrchestrator] = None


def get_settings() -> Settings:
    """Dependency providing Settings instance."""
    return Settings()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency providing a database session lifecycle for API requests.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_orchestrator() -> FinancialOrchestrator:
    """
    Dependency providing singleton FinancialOrchestrator instance.
    """
    global _orchestrator_instance
    if _orchestrator_instance is None:
        logger.info("Initializing singleton FinancialOrchestrator instance for FastAPI dependencies.")
        _orchestrator_instance = FinancialOrchestrator()
    return _orchestrator_instance


def get_current_user_or_guest(
    request: Request,
    response: Response,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Tuple[Optional[User], Optional[GuestSession]]:
    """
    Unified dual-auth dependency.
    1. Attempts to authenticate user via Bearer JWT token in Authorization header.
    2. If no valid Bearer token, falls back to stateless GuestSession cookie.

    Returns:
        Tuple of (User | None, GuestSession | None).
    """
    # 1. Try Bearer JWT Authentication
    if auth and auth.credentials:
        payload = decode_access_token(auth.credentials)
        if payload:
            user_id = payload.get("user_id")
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    logger.info(f"Authenticated user request: ID={user.id}, email='{user.email}'")
                    return user, None

    # 2. Fallback to Guest Session Cookie
    logger.info("No valid Bearer JWT header found. Falling back to Guest Session cookie...")
    guest = get_guest_session(request, response)
    return None, guest


def get_current_user(
    request: Request,
    response: Response,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency requiring an authenticated user, raising HTTP 401 if missing."""
    user, _ = get_current_user_or_guest(request, response, auth, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access this resource."
        )
    return user


def get_optional_user(
    request: Request,
    response: Response,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Dependency returning User instance if authenticated, or None if guest."""
    user, _ = get_current_user_or_guest(request, response, auth, db)
    return user
