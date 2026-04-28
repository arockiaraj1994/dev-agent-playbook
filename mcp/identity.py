"""
identity.py — Resolve the caller's identity for HTTP requests to /sse and
/dashboard, then expose it through context vars to async code below.

Two modes, controlled by a single config flag (`auth.enabled`):

  * **auth on** — Bearer token validated via Keycloak token introspection.
    The introspection response's `sub` becomes user_id; `username` /
    `preferred_username` becomes user_name.

  * **auth off** — best-effort identification suitable for an internal trust
    environment:
      1. `X-MCP-User` header (or `?user=` query param) — advisory but
         lets users opt in to having their name in the dashboard.
      2. Otherwise, fall back to a synthetic id derived from the client IP.

The resolved identity is attached to the ASGI `scope["state"]["principal"]`
and propagated into Python contextvars so MCP tool handlers can read it
without plumbing arguments through the SDK.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass

import httpx
from starlette.types import Receive, Scope, Send

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Principal:
    user_id: str
    user_name: str


@dataclass(frozen=True)
class EditorInfo:
    name: str = ""
    version: str = ""


# ---------------------------------------------------------------------------
# Context vars (read by tool handlers / metrics recorder)
# ---------------------------------------------------------------------------


principal_var: ContextVar[Principal | None] = ContextVar(
    "principal",
    default=None,
)
# EditorInfo is frozen, so this default is effectively immutable. The B039
# rule is conservative and doesn't recognise that.
editor_var: ContextVar[EditorInfo] = ContextVar(
    "editor",
    default=EditorInfo(),  # noqa: B039
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _header(scope: Scope, name: str) -> str | None:
    """Return the *first* value of header `name` from the ASGI scope."""
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
    """Identity derivation when auth is disabled."""
    name = (_header(scope, "x-mcp-user") or _query_param(scope, "user") or "").strip()
    if name:
        return Principal(user_id=f"hdr:{name}", user_name=name)
    ip = _client_ip(scope)
    return Principal(user_id=f"ip:{ip}", user_name=f"anon@{ip}")


# ---------------------------------------------------------------------------
# Keycloak introspection helper (auth on)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class KeycloakConfig:
    introspect_url: str
    client_id: str
    client_secret: str


async def _introspect(
    *,
    token: str,
    cfg: KeycloakConfig,
    http_client: httpx.AsyncClient,
) -> Principal | None:
    try:
        resp = await http_client.post(
            cfg.introspect_url,
            data={
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "token": token,
            },
        )
    except httpx.HTTPError as exc:
        logger.exception("Keycloak introspection request failed: %s", exc)
        return None
    if resp.status_code != 200:
        logger.error("Keycloak introspection HTTP %s", resp.status_code)
        return None
    try:
        payload: dict = resp.json()
    except json.JSONDecodeError:
        logger.error("Keycloak introspection returned non-JSON")
        return None
    if payload.get("active") is not True:
        return None

    user_id = str(
        payload.get("sub") or payload.get("client_id") or "unknown",
    )
    user_name = str(
        payload.get("preferred_username")
        or payload.get("username")
        or payload.get("email")
        or user_id,
    )
    return Principal(user_id=user_id, user_name=user_name)


# ---------------------------------------------------------------------------
# ASGI middleware: attach identity to scope and reject 401 when auth is on
# ---------------------------------------------------------------------------


async def _send_json_status(send: Send, status: int, body: dict) -> None:
    raw = json.dumps(body).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(raw)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": raw})


class IdentityMiddleware:
    """
    ASGI middleware that attaches a Principal to scope["state"]["principal"].

    When `auth_enabled` is True, requests without a valid Keycloak Bearer
    token are rejected with 401. Otherwise identity is best-effort.
    """

    def __init__(
        self,
        app,
        *,
        auth_enabled: bool,
        keycloak: KeycloakConfig | None,
        http_client: httpx.AsyncClient | None,
    ) -> None:
        if auth_enabled and (keycloak is None or http_client is None):
            raise ValueError(
                "auth_enabled=True requires both keycloak config and http_client",
            )
        self._app = app
        self._auth_enabled = auth_enabled
        self._keycloak = keycloak
        self._http_client = http_client

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        principal = await self._resolve(scope, send)
        if principal is None:
            return  # response already sent

        state = scope.setdefault("state", {})
        state["principal"] = principal
        token = principal_var.set(principal)
        try:
            await self._app(scope, receive, send)
        finally:
            principal_var.reset(token)

    async def _resolve(self, scope: Scope, send: Send) -> Principal | None:
        if not self._auth_enabled:
            return _anonymous_principal(scope)

        token = _bearer_token(scope)
        if token is None:
            await _send_json_status(
                send,
                401,
                {"error": "invalid_token", "error_description": "Authentication required"},
            )
            return None

        assert self._keycloak is not None and self._http_client is not None
        principal = await _introspect(
            token=token,
            cfg=self._keycloak,
            http_client=self._http_client,
        )
        if principal is None:
            await _send_json_status(
                send,
                401,
                {"error": "invalid_token", "error_description": "Token rejected"},
            )
            return None
        return principal


def scope_principal(scope: Scope) -> Principal | None:
    """Convenience accessor for ASGI app code."""
    state = scope.get("state") or {}
    return state.get("principal")
