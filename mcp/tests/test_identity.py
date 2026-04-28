"""Tests for identity.py — anonymous fallback, header parsing, middleware."""

from __future__ import annotations

import pytest

from identity import (
    Principal,
    _anonymous_principal,
    _bearer_token,
    _client_ip,
    _header,
    _query_param,
)


def _scope(
    headers: list[tuple[bytes, bytes]] | None = None,
    query: bytes = b"",
    client: tuple[str, int] | None = None,
) -> dict:
    return {
        "type": "http",
        "headers": headers or [],
        "query_string": query,
        "client": client,
    }


def test_header_lookup_case_insensitive() -> None:
    s = _scope(headers=[(b"X-MCP-User", b"alice")])
    assert _header(s, "x-mcp-user") == "alice"
    assert _header(s, "X-MCP-User") == "alice"


def test_header_missing_returns_none() -> None:
    assert _header(_scope(), "x-mcp-user") is None


def test_query_param_extraction() -> None:
    s = _scope(query=b"foo=1&user=alice&bar=2")
    assert _query_param(s, "user") == "alice"
    assert _query_param(s, "missing") is None


def test_client_ip_prefers_xff() -> None:
    s = _scope(headers=[(b"x-forwarded-for", b"10.0.0.1, 192.168.1.1")])
    assert _client_ip(s) == "10.0.0.1"


def test_client_ip_falls_back_to_scope_client() -> None:
    s = _scope(client=("172.20.0.5", 1234))
    assert _client_ip(s) == "172.20.0.5"


def test_client_ip_unknown_when_nothing_available() -> None:
    assert _client_ip(_scope()) == "unknown"


def test_bearer_token_extraction() -> None:
    s = _scope(headers=[(b"authorization", b"Bearer abc.def.ghi")])
    assert _bearer_token(s) == "abc.def.ghi"


def test_bearer_token_rejects_other_schemes() -> None:
    s = _scope(headers=[(b"authorization", b"Basic dXNlcjpwYXNz")])
    assert _bearer_token(s) is None


def test_bearer_token_handles_whitespace_and_empty() -> None:
    s = _scope(headers=[(b"authorization", b"Bearer   ")])
    assert _bearer_token(s) is None


def test_anonymous_principal_uses_x_mcp_user() -> None:
    s = _scope(headers=[(b"x-mcp-user", b"alice")])
    p = _anonymous_principal(s)
    assert isinstance(p, Principal)
    assert p.user_name == "alice"
    assert p.user_id.startswith("hdr:")


def test_anonymous_principal_uses_query_user() -> None:
    s = _scope(query=b"user=bob")
    p = _anonymous_principal(s)
    assert p.user_name == "bob"


def test_anonymous_principal_falls_back_to_ip() -> None:
    s = _scope(client=("10.1.2.3", 5000))
    p = _anonymous_principal(s)
    assert p.user_id == "ip:10.1.2.3"
    assert p.user_name == "anon@10.1.2.3"


# -- editor detection (from server.py — lives close to identity in spirit) --


def test_editor_from_user_agent_known_clients() -> None:
    from server import editor_from_user_agent

    assert editor_from_user_agent("claude-code/1.2.3 (linux)").name == "claude-code"
    assert editor_from_user_agent("Cursor/0.42").name == "cursor"
    assert editor_from_user_agent("Windsurf 1.0.0 +https://...").name == "windsurf"


def test_editor_from_user_agent_extracts_version() -> None:
    from server import editor_from_user_agent

    e = editor_from_user_agent("claude-code/1.2.3 (linux x86_64)")
    assert e.version == "1.2.3"


def test_editor_from_user_agent_unknown() -> None:
    from server import editor_from_user_agent

    assert editor_from_user_agent(None).name == "unknown"
    assert editor_from_user_agent("").name == "unknown"
    e = editor_from_user_agent("SomethingElse/9")
    assert e.name == "somethingelse"


@pytest.mark.asyncio
async def test_identity_middleware_anonymous(tmp_path) -> None:
    from identity import IdentityMiddleware, principal_var

    captured: list[Principal | None] = []

    async def app(scope, receive, send):
        captured.append(principal_var.get())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = IdentityMiddleware(app, auth_enabled=False, keycloak=None, http_client=None)
    scope = {
        "type": "http",
        "headers": [(b"x-mcp-user", b"alice")],
        "query_string": b"",
    }
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    await mw(scope, receive, send)
    assert captured[0] is not None
    assert captured[0].user_name == "alice"
    assert sent[0]["status"] == 204


@pytest.mark.asyncio
async def test_identity_middleware_auth_required_returns_401() -> None:
    import httpx

    from identity import IdentityMiddleware, KeycloakConfig

    async def app(scope, receive, send):
        raise AssertionError("inner app should not be called")

    async with httpx.AsyncClient() as client:
        mw = IdentityMiddleware(
            app,
            auth_enabled=True,
            keycloak=KeycloakConfig(
                introspect_url="https://example.invalid/i",
                client_id="x",
                client_secret="y",
            ),
            http_client=client,
        )
        sent: list = []

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async def send(msg):
            sent.append(msg)

        scope = {"type": "http", "headers": [], "query_string": b""}
        await mw(scope, receive, send)

    assert sent[0]["status"] == 401
