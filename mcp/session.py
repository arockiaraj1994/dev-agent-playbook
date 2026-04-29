"""
session.py — Dashboard browser session management.

Responsibility: HttpOnly cookie sessions and CSRF protection for /dashboard/*,
/login, and /logout. Completely separate from MCP Bearer-token auth (identity.py).

Cookie spec:
  Name:     session
  HttpOnly: True   — JS cannot read it (XSS protection)
  SameSite: Strict — blocks cross-site requests
  Secure:   True when served over HTTPS
  Max-Age:  derived from token expires_at, omitted if Unlimited
  Path:     /

CSRF spec (double-submit cookie pattern):
  csrf_token cookie (NOT HttpOnly, SameSite=Strict) set on GET requests.
  Every POST form includes <input type="hidden" name="_csrf" value="{{ csrf_token }}">.
  Validated via secrets.compare_digest — constant-time comparison.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from starlette.types import Scope

if TYPE_CHECKING:
    from auth import AuthStore

from identity import Principal

_SESSION_COOKIE = "session"
_CSRF_COOKIE = "csrf_token"


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def _read_cookie(scope: Scope, name: str) -> str | None:
    """Extract a named cookie value from the ASGI scope headers."""
    for k, v in scope.get("headers") or []:
        if k.lower() == b"cookie":
            raw = v.decode("latin-1")
            for part in raw.split(";"):
                part = part.strip()
                if part.startswith(f"{name}="):
                    return part[len(name) + 1 :]
    return None


def _build_cookie(
    name: str,
    value: str,
    *,
    http_only: bool,
    secure: bool,
    max_age: int | None,
    path: str = "/",
) -> str:
    parts = [f"{name}={value}", f"Path={path}", "SameSite=Strict"]
    if http_only:
        parts.append("HttpOnly")
    if secure:
        parts.append("Secure")
    if max_age is not None:
        parts.append(f"Max-Age={max_age}")
    return "; ".join(parts)


def _expires_to_max_age(expires_at: str | None) -> int | None:
    """Convert ISO expires_at to Max-Age seconds. None means no expiry (Unlimited)."""
    if expires_at is None:
        return None
    try:
        exp = datetime.fromisoformat(expires_at)
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=UTC)
        delta = int((exp - datetime.now(UTC)).total_seconds())
        return max(delta, 1)
    except (ValueError, OSError):
        return None


# ---------------------------------------------------------------------------
# DashboardSession
# ---------------------------------------------------------------------------


class DashboardSession:
    """
    Manages HttpOnly cookie sessions and CSRF tokens for the dashboard.

    Instantiated once at startup and injected into route handlers that need it.
    """

    def __init__(self, auth_store: "AuthStore") -> None:
        self._auth_store = auth_store

    # -- Session cookie resolution -------------------------------------------

    async def resolve_cookie(self, scope: Scope) -> Principal | None:
        """
        Read the session cookie and validate it against the AuthStore
        (token_type="session"). Returns None if missing or invalid — the
        caller is responsible for sending a redirect to /login.
        """
        token = _read_cookie(scope, _SESSION_COOKIE)
        if not token:
            return None
        return await self._auth_store.resolve_token(token, token_type="session")

    # -- Cookie write helpers (called from auth_routes.py) -------------------

    def session_cookie_header(
        self,
        token: str,
        expires_at: str | None,
        *,
        secure: bool = False,
    ) -> tuple[bytes, bytes]:
        """Return a (b'set-cookie', value) header tuple for the session cookie."""
        value = _build_cookie(
            _SESSION_COOKIE,
            token,
            http_only=True,
            secure=secure,
            max_age=_expires_to_max_age(expires_at),
        )
        return (b"set-cookie", value.encode("latin-1"))

    def clear_session_cookie_header(self, *, secure: bool = False) -> tuple[bytes, bytes]:
        """Return a Set-Cookie header that expires the session cookie immediately."""
        value = _build_cookie(
            _SESSION_COOKIE,
            "",
            http_only=True,
            secure=secure,
            max_age=0,
        )
        return (b"set-cookie", value.encode("latin-1"))

    # -- CSRF ----------------------------------------------------------------

    @staticmethod
    def generate_csrf_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_csrf(cookie_val: str | None, form_val: str | None) -> bool:
        """Constant-time comparison. Returns False if either value is absent."""
        if not cookie_val or not form_val:
            return False
        return secrets.compare_digest(cookie_val, form_val)

    def refresh_cookie_header(
        self,
        token: str,
        *,
        secure: bool = False,
        idle_minutes: int = 60,
    ) -> tuple[bytes, bytes]:
        """Re-issue the session cookie with a fresh Max-Age to slide the idle window."""
        value = _build_cookie(
            _SESSION_COOKIE,
            token,
            http_only=True,
            secure=secure,
            max_age=idle_minutes * 60,
        )
        return (b"set-cookie", value.encode("latin-1"))

    @staticmethod
    def csrf_cookie_header(token: str, *, secure: bool = False) -> tuple[bytes, bytes]:
        """Return a (b'set-cookie', value) header for the CSRF cookie (NOT HttpOnly)."""
        parts = [f"{_CSRF_COOKIE}={token}", "Path=/", "SameSite=Strict"]
        if secure:
            parts.append("Secure")
        value = "; ".join(parts)
        return (b"set-cookie", value.encode("latin-1"))

    @staticmethod
    def read_csrf_cookie(scope: Scope) -> str | None:
        return _read_cookie(scope, _CSRF_COOKIE)
