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


async def get_current_user_or_guest(
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

    if guest:
        client_ip = request.client.host if request.client else "127.0.0.1"
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        try:
            redis = await RedisClient.get_client()
            if redis:
                ip_key = f"rate_limit:guest:ip:{client_ip}:{today_str}"
                count_str = await redis.get(ip_key)
                if count_str is not None:
                    ip_count = int(count_str)
                    guest.queries_used = ip_count
                    guest.queries_remaining = max(0, 15 - ip_count)
                    
                    # Update signed cookie with synced Redis count
                    handler = GuestCookieHandler()
                    signed_val = handler.sign_cookie_payload(guest)
                    response.set_cookie(
                        key="guest_session",
                        value=signed_val,
                        max_age=60 * 60 * 24 * 30,
                        httponly=True,
                        samesite="lax",
                    )
        except Exception as e:
            logger.warning(f"Failed to sync guest session with Redis IP rate limit: {e}")

    return None, guest


async def get_current_user(
    request: Request,
    response: Response,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """Dependency requiring an authenticated user, raising HTTP 401 if missing."""
    user, _ = await get_current_user_or_guest(request, response, auth, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to access this resource."
        )
    return user


async def get_optional_user(
    request: Request,
    response: Response,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Dependency returning User instance if authenticated, or None if guest."""
    user, _ = await get_current_user_or_guest(request, response, auth, db)
    return user


import datetime
from app.models import UserRateLimit
from app.cache import RedisClient

async def enforce_rate_limit(
    request: Request,
    response: Response,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Tuple[Optional[User], Optional[GuestSession]]:
    """
    Enforces daily rate limits:
    - 45 queries for logged-in users
    - 15 queries for guests
    """
    user, guest = await get_current_user_or_guest(request, response, auth, db)
    
    if user:
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        rate_limit = db.query(UserRateLimit).filter(UserRateLimit.user_id == user.id).first()
        
        if not rate_limit:
            rate_limit = UserRateLimit(user_id=user.id, queries_used=0, last_reset_date=today_str)
            db.add(rate_limit)
        
        if rate_limit.last_reset_date != today_str:
            rate_limit.queries_used = 0
            rate_limit.last_reset_date = today_str
            
        if rate_limit.queries_used >= 45:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="USER_LIMIT_REACHED"
            )
            
        rate_limit.queries_used += 1
        db.commit()
        return user, None
        
    # Daily Rate Limit for Guests (IP based tracking)
    if not user:
        client_ip = request.client.host if request.client else "127.0.0.1"
        today_str = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
        
        redis = await RedisClient.get_client()
        if redis:
            ip_key = f"rate_limit:guest:ip:{client_ip}:{today_str}"
            current_count = await redis.incr(ip_key)
            if current_count == 1:
                await redis.expire(ip_key, 86400)  # 24 hours
            
            if guest:
                guest.queries_used = current_count
                guest.queries_remaining = max(0, 15 - current_count)
                
                handler = GuestCookieHandler()
                signed_val = handler.sign_cookie_payload(guest)
                response.set_cookie(
                    key="guest_session",
                    value=signed_val,
                    max_age=60 * 60 * 24 * 30,
                    httponly=True,
                    samesite="lax",
                )
                
                if current_count > 15:
                    logger.warning(f"Guest IP {client_ip} exceeded daily query limit of 15.")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="GUEST_LIMIT_REACHED"
                    )
            else:
                if current_count > 15:
                    logger.warning(f"Guest IP {client_ip} exceeded daily query limit of 15.")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="GUEST_LIMIT_REACHED"
                    )
        else:
            # Fallback to guest session cookie if Redis is not running
            if guest:
                if guest.queries_used >= 15:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="GUEST_LIMIT_REACHED"
                    )
                guest.queries_used += 1
                guest.queries_remaining = max(0, 15 - guest.queries_used)
                handler = GuestCookieHandler()
                signed_val = handler.sign_cookie_payload(guest)
                response.set_cookie(
                    key="guest_session",
                    value=signed_val,
                    max_age=60 * 60 * 24 * 30,
                    httponly=True,
                    samesite="lax",
                )
        return None, guest
        
    return None, None
