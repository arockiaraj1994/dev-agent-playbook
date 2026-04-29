"""
identity.py — MCP identity resolution for /sse and /messages/ requests.

Responsibility: validate Authorization: Bearer <token> headers against the
AuthStore (token_type="mcp") and resolve them to a Principal.

Dashboard/browser identity is handled separately in session.py.

Two modes, controlled by auth_enabled:
  * auth on  — Bearer token validated via AuthStore; 401 if missing or invalid.
  * auth off — best-effort: X-MCP-User header, ?user= param, or client IP.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.types import Receive, Scope, Send

if TYPE_CHECKING:
    from auth import AuthStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Principal:
    user_id: str
    user_name: str
    role: str = "user"


@dataclass(frozen=True)
class EditorInfo:
    name: str = ""
    version: str = ""


# ---------------------------------------------------------------------------
# Context vars (read by tool handlers / metrics recorder)
# ---------------------------------------------------------------------------


principal_var: ContextVar[Principal | None] = ContextVar("principal", default=None)
# EditorInfo is frozen, so this default is effectively immutable.
editor_var: ContextVar[EditorInfo] = ContextVar(
    "editor",
    default=EditorInfo(),  # noqa: B039
)


# ---------------------------------------------------------------------------
# Header / query / IP helpers
# ---------------------------------------------------------------------------


def _header(scope: Scope, name: str) -> str | None:
    target = name.lower().encode("latin-1")
    for k, v in scope.get("headers") or []:
        if k.lower() == target:
            return v.decode("latin-1")
    return None


def _query_param(scope: Scope, key: str) -> str | None:
    raw = scope.get("query_string") or b""
    if not raw:
        return None
    needle = f"{key}=".encode()
    for chunk in raw.split(b"&"):
        if chunk.startswith(needle):
            return chunk[len(needle) :].decode("latin-1", errors="replace")
    return None


def _client_ip(scope: Scope) -> str:
    fwd = _header(scope, "x-forwarded-for")
    if fwd:
        return fwd.split(",", 1)[0].strip()
    client = scope.get("client")
    if client and isinstance(client, (tuple, list)) and client:
        return str(client[0])
    return "unknown"


def _bearer_token(scope: Scope) -> str | None:
    raw = _header(scope, "authorization")
    if not raw or not raw.lower().startswith("bearer "):
        return None
    token = raw[7:].strip()
    return token or None


# ---------------------------------------------------------------------------
# Anonymous identity (auth off)
# ---------------------------------------------------------------------------


def _anonymous_principal(scope: Scope) -> Principal:
    """Best-effort identity when auth is disabled."""
    name = (_header(scope, "x-mcp-user") or _query_param(scope, "user") or "").strip()
    if name:
        return Principal(user_id=f"hdr:{name}", user_name=name, role="user")
    ip = _client_ip(scope)
    return Principal(user_id=f"ip:{ip}", user_name=f"anon@{ip}", role="user")


# ---------------------------------------------------------------------------
# JSON 401 helper
# ---------------------------------------------------------------------------


async def send_json_401(send: Send, description: str) -> None:
    body = json.dumps({"error": "invalid_token", "error_description": description}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


# ---------------------------------------------------------------------------
# MCP Bearer token resolution (called by AppAuthMiddleware in server.py)
# ---------------------------------------------------------------------------


async def resolve_bearer_token(
    scope: Scope,
    send: Send,
    auth_store: "AuthStore",
    auth_enabled: bool,
) -> Principal | None:
    """
    Resolve a Bearer token for MCP paths (/sse, /messages/).

    Returns a Principal on success, or None after sending a 401 response.
    When auth is disabled, returns an anonymous principal.
    """
    if not auth_enabled:
        return _anonymous_principal(scope)

    token = _bearer_token(scope)
    if token is None:
        await send_json_401(send, "Authentication required")
        return None

    principal = await auth_store.resolve_token(token, token_type="mcp")
    if principal is None:
        await send_json_401(send, "Token rejected or expired")
        return None

    return principal


# ---------------------------------------------------------------------------
# Scope accessor
# ---------------------------------------------------------------------------


def scope_principal(scope: Scope) -> Principal | None:
    state = scope.get("state") or {}
    return state.get("principal")
