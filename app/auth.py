from __future__ import annotations

# Merged from auth/*

from app.config.settings import Settings
from app.utils import get_logger
from fastapi import HTTPException, Request, Response, status
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, Optional
import base64
import datetime
import hashlib
import hmac
import json
import uuid



"""
Stateless Guest Mode Security Module for FinnAI Platform.
Tracks guest query usage using signed HMAC-SHA256 cookies without requiring database storage.
Enforces GUEST_QUERY_LIMIT (Default: 3 queries) and manages Guest Purpose of Visit onboarding.
"""



logger = get_logger("finnai.auth.guest")


class GuestSession(BaseModel):
    """
    Stateless Guest Session container schema.
    """

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique guest session UUID.")
    queries_used: int = Field(default=0, description="Number of queries executed so far.")
    queries_remaining: int = Field(default=-1, description="Number of free guest queries remaining (-1 = Unlimited).")
    purpose_of_visit: Optional[str] = Field(default=None, description="Optional guest stated purpose of visit.")
    created_at: str = Field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat(),
        description="UTC ISO 8601 timestamp of session creation.",
    )

    model_config = ConfigDict(from_attributes=True)


class GuestCookieHandler:
    """
    Helper providing HMAC-SHA256 signature signing and parsing for guest_session cookies.
    """

    def __init__(self, secret_key: Optional[str] = None) -> None:
        self.settings = Settings()
        self.secret_key = secret_key or self.settings.secret_key or "finnai-guest-secret-2026"
        self.limit = -1  # -1 = Unlimited guest queries

    @property
    def secret_bytes(self) -> bytes:
        return self.secret_key.encode("utf-8")

    def _b64_encode(self, data_bytes: bytes) -> str:
        return base64.urlsafe_b64encode(data_bytes).decode("utf-8").rstrip("=")

    def _b64_decode(self, b64_str: str) -> bytes:
        padding = "=" * ((4 - len(b64_str) % 4) % 4)
        return base64.urlsafe_b64decode((b64_str + padding).encode("utf-8"))

    def sign_cookie_payload(self, session: GuestSession) -> str:
        """
        Encode and sign a GuestSession payload.
        """
        payload_data = {
            "sid": session.session_id,
            "used": session.queries_used,
            "purpose": session.purpose_of_visit,
            "cat": session.created_at,
        }
        json_bytes = json.dumps(payload_data, separators=(",", ":")).encode("utf-8")
        encoded_payload = self._b64_encode(json_bytes)

        signature = hmac.new(self.secret_bytes, encoded_payload.encode("utf-8"), hashlib.sha256).digest()
        encoded_sig = self._b64_encode(signature)

        return f"{encoded_payload}.{encoded_sig}"

    def parse_cookie_payload(self, cookie_value: str) -> Optional[GuestSession]:
        """
        Verify signature and parse GuestSession payload.
        """
        try:
            parts = cookie_value.split(".")
            if len(parts) != 2:
                return None

            encoded_payload, encoded_sig = parts
            expected_sig = hmac.new(self.secret_bytes, encoded_payload.encode("utf-8"), hashlib.sha256).digest()
            actual_sig = self._b64_decode(encoded_sig)

            if not hmac.compare_digest(expected_sig, actual_sig):
                logger.warning("Guest cookie HMAC signature mismatch!")
                return None

            json_bytes = self._b64_decode(encoded_payload)
            data = json.loads(json_bytes.decode("utf-8"))

            queries_used = data.get("used", 0)

            return GuestSession(
                session_id=data.get("sid", str(uuid.uuid4())),
                queries_used=queries_used,
                queries_remaining=-1,
                purpose_of_visit=data.get("purpose"),
                created_at=data.get("cat", datetime.datetime.now(datetime.timezone.utc).isoformat()),
            )
        except Exception as e:
            logger.warning(f"Failed to parse guest cookie: {e}")
            return None


_cookie_handler = GuestCookieHandler()


def get_guest_session(request: Request, response: Response) -> GuestSession:
    """
    FastAPI dependency managing guest sessions with unlimited query access.
    """
    cookie_val = request.cookies.get("guest_session")
    session = _cookie_handler.parse_cookie_payload(cookie_val) if cookie_val else None

    if session is None:
        session = GuestSession()

    # Increment queries_used for current request
    session.queries_used += 1
    session.queries_remaining = -1

    # Set updated signed cookie in response
    signed_val = _cookie_handler.sign_cookie_payload(session)
    response.set_cookie(
        key="guest_session",
        value=signed_val,
        max_age=60 * 60 * 24 * 30,  # 30 days
        httponly=True,
        samesite="lax",
    )

    logger.info(f"Guest session '{session.session_id}' query allowed (unlimited).")
    return session

"""
JWT Token Handler for FinnAI Platform.
Generates and decodes signed Bearer JWT access tokens using HMAC-SHA256 signature.
"""


logger = get_logger("finnai.auth.jwt")


class JWTHandler:
    """
    Handles JWT access token creation and HMAC-SHA256 signature verification.
    """

    def __init__(self, secret_key: Optional[str] = None) -> None:
        settings = Settings()
        self.secret_key = secret_key or os_secret or settings.secret_key or "finnai-super-secret-key-2026"

    @property
    def secret_bytes(self) -> bytes:
        return self.secret_key.encode("utf-8")

    def _b64_encode(self, data_bytes: bytes) -> str:
        return base64.urlsafe_b64encode(data_bytes).decode("utf-8").rstrip("=")

    def _b64_decode(self, b64_str: str) -> bytes:
        padding = "=" * ((4 - len(b64_str) % 4) % 4)
        return base64.urlsafe_b64decode((b64_str + padding).encode("utf-8"))

    def create_access_token(
        self, data: Dict[str, Any], expires_minutes: int = 60 * 24 * 7
    ) -> str:
        """
        Create a signed JWT access token.

        Args:
            data: Payload dictionary (e.g. {'user_id': 1, 'email': 'user@example.com'}).
            expires_minutes: Token validity in minutes (Default: 7 days).

        Returns:
            JWT token string (header.payload.signature).
        """
        header = {"alg": "HS256", "typ": "JWT"}
        exp_timestamp = (
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(minutes=expires_minutes)
        ).timestamp()

        payload = dict(data)
        payload["exp"] = int(exp_timestamp)
        payload["iat"] = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

        header_json = json.dumps(header, separators=(",", ":")).encode("utf-8")
        payload_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")

        encoded_header = self._b64_encode(header_json)
        encoded_payload = self._b64_encode(payload_json)

        unsigned_token = f"{encoded_header}.{encoded_payload}"
        signature = hmac.new(self.secret_bytes, unsigned_token.encode("utf-8"), hashlib.sha256).digest()
        encoded_signature = self._b64_encode(signature)

        return f"{unsigned_token}.{encoded_signature}"

    def decode_access_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify signature and expiration of a JWT access token.

        Args:
            token: JWT token string.

        Returns:
            Payload dictionary if valid, None if invalid or expired.
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            encoded_header, encoded_payload, encoded_signature = parts
            unsigned_token = f"{encoded_header}.{encoded_payload}"

            expected_sig = hmac.new(self.secret_bytes, unsigned_token.encode("utf-8"), hashlib.sha256).digest()
            actual_sig = self._b64_decode(encoded_signature)

            if not hmac.compare_digest(expected_sig, actual_sig):
                logger.warning("JWT signature verification failed.")
                return None

            payload_bytes = self._b64_decode(encoded_payload)
            payload = json.loads(payload_bytes.decode("utf-8"))

            exp = payload.get("exp")
            if exp and datetime.datetime.now(datetime.timezone.utc).timestamp() > exp:
                logger.warning("JWT token is expired.")
                return None

            return payload

        except Exception as e:
            logger.warning(f"Failed to decode JWT token: {e}")
            return None


# Helper instance
os_secret = None
_handler = JWTHandler()


def create_access_token(data: Dict[str, Any], expires_minutes: int = 60 * 24 * 7) -> str:
    return _handler.create_access_token(data, expires_minutes)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    return _handler.decode_access_token(token)
