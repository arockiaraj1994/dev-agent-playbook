"""Tests for identity.py (MCP Bearer auth) and server.AppAuthMiddleware."""

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
    path: str = "/sse",
) -> dict:
    return {
        "type": "http",
        "headers": headers or [],
        "query_string": query,
        "client": client,
        "path": path,
    }


# ---------------------------------------------------------------------------
# Header / IP / bearer helpers
# ---------------------------------------------------------------------------


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
    assert p.role == "user"


def test_anonymous_principal_uses_query_user() -> None:
    s = _scope(query=b"user=bob")
    p = _anonymous_principal(s)
    assert p.user_name == "bob"


def test_anonymous_principal_falls_back_to_ip() -> None:
    s = _scope(client=("10.1.2.3", 5000))
    p = _anonymous_principal(s)
    assert p.user_id == "ip:10.1.2.3"
    assert p.user_name == "anon@10.1.2.3"


# ---------------------------------------------------------------------------
# Editor detection
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# AppAuthMiddleware — anonymous (auth off)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_auth_middleware_anonymous(tmp_path) -> None:
    from auth import AuthStore
    from server import AppAuthMiddleware
    from session import DashboardSession
    from identity import principal_var

    auth_store = AuthStore(tmp_path / "auth.db")
    await auth_store.init()
    dashboard_session = DashboardSession(auth_store)

    captured: list[Principal | None] = []

    async def app(scope, receive, send):
        captured.append(principal_var.get())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = AppAuthMiddleware(
        app,
        auth_enabled=False,
        auth_store=auth_store,
        dashboard_session=dashboard_session,
    )
    scope = {
        "type": "http",
        "headers": [(b"x-mcp-user", b"alice")],
        "query_string": b"",
        "path": "/sse",
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


# ---------------------------------------------------------------------------
# AppAuthMiddleware — MCP path, auth on, no token → 401
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_auth_middleware_mcp_no_token_returns_401(tmp_path) -> None:
    from auth import AuthStore
    from server import AppAuthMiddleware
    from session import DashboardSession

    auth_store = AuthStore(tmp_path / "auth.db")
    await auth_store.init()
    dashboard_session = DashboardSession(auth_store)

    async def app(scope, receive, send):
        raise AssertionError("inner app should not be called")

    mw = AppAuthMiddleware(
        app,
        auth_enabled=True,
        auth_store=auth_store,
        dashboard_session=dashboard_session,
    )
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "http", "headers": [], "query_string": b"", "path": "/sse"}
    await mw(scope, receive, send)
    assert sent[0]["status"] == 401


# ---------------------------------------------------------------------------
# AppAuthMiddleware — MCP path, valid Bearer token → 204
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_auth_middleware_valid_mcp_token(tmp_path) -> None:
    from auth import AuthStore
    from server import AppAuthMiddleware
    from session import DashboardSession
    from identity import principal_var

    auth_store = AuthStore(tmp_path / "auth.db")
    await auth_store.init()
    await auth_store.seed_default_admin("admin", "secret")
    user = await auth_store.verify_login("admin", "secret")
    token_data = await auth_store.create_token(user["id"], None, token_type="mcp")
    token = token_data["token"]

    dashboard_session = DashboardSession(auth_store)
    captured: list[Principal | None] = []

    async def app(scope, receive, send):
        captured.append(principal_var.get())
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = AppAuthMiddleware(
        app,
        auth_enabled=True,
        auth_store=auth_store,
        dashboard_session=dashboard_session,
    )
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "query_string": b"",
        "path": "/sse",
    }
    await mw(scope, receive, send)
    assert sent[0]["status"] == 204
    assert captured[0].user_name == "admin"
    assert captured[0].role == "admin"


# ---------------------------------------------------------------------------
# AppAuthMiddleware — session token in Bearer header → 401 (type mismatch)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_token_rejected_on_mcp_path(tmp_path) -> None:
    from auth import AuthStore
    from server import AppAuthMiddleware
    from session import DashboardSession

    auth_store = AuthStore(tmp_path / "auth.db")
    await auth_store.init()
    await auth_store.seed_default_admin("admin", "pw")
    user = await auth_store.verify_login("admin", "pw")
    token_data = await auth_store.create_token(user["id"], None, token_type="session")
    token = token_data["token"]

    dashboard_session = DashboardSession(auth_store)

    async def app(scope, receive, send):
        raise AssertionError("inner app should not be called")

    mw = AppAuthMiddleware(
        app,
        auth_enabled=True,
        auth_store=auth_store,
        dashboard_session=dashboard_session,
    )
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {
        "type": "http",
        "headers": [(b"authorization", f"Bearer {token}".encode())],
        "query_string": b"",
        "path": "/sse",
    }
    await mw(scope, receive, send)
    assert sent[0]["status"] == 401


# ---------------------------------------------------------------------------
# AppAuthMiddleware — /auth/login public path → no auth check
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_path_bypasses_auth(tmp_path) -> None:
    from auth import AuthStore
    from server import AppAuthMiddleware
    from session import DashboardSession

    auth_store = AuthStore(tmp_path / "auth.db")
    await auth_store.init()
    dashboard_session = DashboardSession(auth_store)

    inner_called = []

    async def app(scope, receive, send):
        inner_called.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = AppAuthMiddleware(
        app,
        auth_enabled=True,
        auth_store=auth_store,
        dashboard_session=dashboard_session,
    )
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "http", "headers": [], "query_string": b"", "path": "/auth/login"}
    await mw(scope, receive, send)
    assert inner_called
    assert sent[0]["status"] == 200


# ---------------------------------------------------------------------------
# AppAuthMiddleware — /dashboard with no cookie → 302 redirect to /login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unknown_login_prefixed_path_does_not_hit_dashboard_branch(tmp_path) -> None:
    """`/loginx` must not be treated as a login/dashboard route just because it starts with /login."""
    from auth import AuthStore
    from server import AppAuthMiddleware
    from session import DashboardSession

    auth_store = AuthStore(tmp_path / "auth.db")
    await auth_store.init()
    dashboard_session = DashboardSession(auth_store)

    inner_called: list[bool] = []

    async def app(scope, receive, send):
        inner_called.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    mw = AppAuthMiddleware(
        app,
        auth_enabled=True,
        auth_store=auth_store,
        dashboard_session=dashboard_session,
    )
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "http", "headers": [], "query_string": b"", "path": "/loginx"}
    await mw(scope, receive, send)
    # Should NOT have sent a 302 redirect to /login (the dashboard branch's behavior).
    # The fallback "anonymous" branch lets it pass through to the inner app.
    assert sent[0]["status"] != 302
    assert inner_called


@pytest.mark.asyncio
async def test_dashboard_no_cookie_redirects_to_login(tmp_path) -> None:
    from auth import AuthStore
    from server import AppAuthMiddleware
    from session import DashboardSession

    auth_store = AuthStore(tmp_path / "auth.db")
    await auth_store.init()
    dashboard_session = DashboardSession(auth_store)

    async def app(scope, receive, send):
        raise AssertionError("inner app should not be called")

    mw = AppAuthMiddleware(
        app,
        auth_enabled=True,
        auth_store=auth_store,
        dashboard_session=dashboard_session,
    )
    sent: list = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(msg):
        sent.append(msg)

    scope = {"type": "http", "headers": [], "query_string": b"", "path": "/dashboard/"}
    await mw(scope, receive, send)
    assert sent[0]["status"] == 302
    location = dict(sent[0]["headers"]).get(b"location", b"").decode()
    assert location.startswith("/login")
