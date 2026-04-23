"""
Authentication helpers:
  - Session-based login for the web UI (signed cookies via itsdangerous)
  - API-key auth for ESP32 endpoints
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from app.config import settings

SESSION_COOKIE = "beetel_session"
SESSION_MAX_AGE = 60 * 60 * 24  # 24 hours

_serializer = URLSafeTimedSerializer(settings.SECRET_KEY)


# ── Custom exception for unauthenticated requests ────────────


class NotAuthenticated(Exception):
    """Raised when a request lacks valid authentication."""
    pass


def setup_auth_exception_handler(app):
    """Register the redirect handler for unauthenticated requests."""

    @app.exception_handler(NotAuthenticated)
    async def _redirect_to_login(request: Request, exc: NotAuthenticated):
        return RedirectResponse("/login", status_code=303)


# ── Session helpers ──────────────────────────────────────────


def create_session_cookie(username: str) -> str:
    """Create a signed session token."""
    return _serializer.dumps({"user": username})


def verify_session_cookie(token: str) -> dict | None:
    """Verify and decode a session token. Returns None if invalid."""
    try:
        return _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


# ── Dependencies ─────────────────────────────────────────────


async def require_login(request: Request):
    """
    FastAPI dependency: ensures the request has a valid admin session.
    Redirects to /login if not authenticated.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise NotAuthenticated()
    data = verify_session_cookie(token)
    if not data:
        raise NotAuthenticated()
    return data


async def require_api_key(request: Request):
    """
    FastAPI dependency: ensures the request carries a valid ESP32 API key.
    """
    api_key = request.headers.get("X-API-Key", "")
    if not settings.ESP32_API_KEY:
        # No key configured — allow all (dev mode)
        return
    if api_key != settings.ESP32_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )

