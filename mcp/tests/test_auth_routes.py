"""Tests for dashboard/auth_routes.py — CSRF, sliding cookie, redirect targets."""

from __future__ import annotations

from pathlib import Path

import pytest

from auth import AuthStore
from dashboard.auth_routes import build_auth_routes
from session import DashboardSession


# ---------------------------------------------------------------------------
# ASGI scaffolding helpers
# ---------------------------------------------------------------------------


class _FakeReceive:
    def __init__(self, body: bytes) -> None:
        self._body = body
        self._sent = False

    async def __call__(self) -> dict:
        if self._sent:
            return {"type": "http.disconnect"}
        self._sent = True
        return {"type": "http.request", "body": self._body, "more_body": False}


def _form_body(fields: dict[str, str]) -> bytes:
    from urllib.parse import urlencode
    return urlencode(fields).encode()


def _scope(method: str, path: str, *, cookie: str = "", body_len: int = 0) -> dict:
    headers = [
        (b"content-type", b"application/x-www-form-urlencoded"),
        (b"content-length", str(body_len).encode()),
    ]
    if cookie:
        headers.append((b"cookie", cookie.encode()))
    return {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers,
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "state": {},
    }


async def _run(handler, scope, receive) -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """Invoke a Starlette endpoint via its underlying request and return status, headers, body."""
    from starlette.requests import Request

    request = Request(scope, receive)
    response = await handler(request)
    sent: list[dict] = []

    async def send(msg: dict) -> None:
        sent.append(msg)

    await response(scope, receive, send)
    start = next(m for m in sent if m["type"] == "http.response.start")
    body_chunks = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return start["status"], start["headers"], body_chunks


@pytest.fixture
async def store(tmp_path: Path) -> AuthStore:
    s = AuthStore(tmp_path / "auth.db")
    await s.init()
    await s.create_user("alice", "pw", "user")
    return s


@pytest.fixture
def session_mgr(store: AuthStore) -> DashboardSession:
    return DashboardSession(store)


@pytest.fixture
def routes(store: AuthStore, session_mgr: DashboardSession):
    return build_auth_routes(store, session_mgr, "test-server")


# ---------------------------------------------------------------------------
# Login CSRF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_post_missing_csrf_returns_403(routes) -> None:
    _, login_post, _ = routes
    body = _form_body({"username": "alice", "password": "pw"})
    scope = _scope("POST", "/login", body_len=len(body))
    status, headers, _ = await _run(login_post, scope, _FakeReceive(body))
    assert status == 403
    # No session cookie should have been set
    assert not any(k == b"set-cookie" and b"session=" in v for k, v in headers)


@pytest.mark.asyncio
async def test_login_post_bad_csrf_returns_403(routes) -> None:
    _, login_post, _ = routes
    body = _form_body({"username": "alice", "password": "pw", "_csrf": "wrong"})
    scope = _scope("POST", "/login", cookie="csrf_token=expected", body_len=len(body))
    status, _, _ = await _run(login_post, scope, _FakeReceive(body))
    assert status == 403


@pytest.mark.asyncio
async def test_login_post_valid_csrf_sets_sliding_cookie(routes) -> None:
    _, login_post, _ = routes
    body = _form_body({"username": "alice", "password": "pw", "_csrf": "tok"})
    scope = _scope("POST", "/login", cookie="csrf_token=tok", body_len=len(body))
    status, headers, _ = await _run(login_post, scope, _FakeReceive(body))
    assert status == 303
    # Session cookie present with sliding 60-min Max-Age
    cookies = [v.decode() for k, v in headers if k == b"set-cookie"]
    session_cookies = [c for c in cookies if c.startswith("session=")]
    assert len(session_cookies) == 1
    assert "Max-Age=3600" in session_cookies[0]
    assert "HttpOnly" in session_cookies[0]


# ---------------------------------------------------------------------------
# Logout CSRF
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_post_missing_csrf_returns_403(routes, store: AuthStore) -> None:
    """Logout must not revoke the session token without a valid CSRF check."""
    _, _, logout_post = routes
    user = await store.verify_login("alice", "pw")
    token_data = await store.create_token(user["id"], None, token_type="session")
    token = token_data["token"]

    body = b""
    scope = _scope("POST", "/logout", cookie=f"session={token}", body_len=0)
    status, _, _ = await _run(logout_post, scope, _FakeReceive(body))
    assert status == 403
    # Token must still resolve — logout was rejected
    assert await store.resolve_token(token, token_type="session") is not None


@pytest.mark.asyncio
async def test_logout_post_valid_csrf_revokes_token(routes, store: AuthStore) -> None:
    _, _, logout_post = routes
    user = await store.verify_login("alice", "pw")
    token_data = await store.create_token(user["id"], None, token_type="session")
    token = token_data["token"]

    body = _form_body({"_csrf": "tok"})
    scope = _scope(
        "POST", "/logout", cookie=f"session={token}; csrf_token=tok", body_len=len(body)
    )
    status, _, _ = await _run(logout_post, scope, _FakeReceive(body))
    assert status == 303
    assert await store.resolve_token(token, token_type="session") is None


# ---------------------------------------------------------------------------
# Login GET renders CSRF input + URL-encoded next
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_get_renders_csrf_input(routes) -> None:
    login_get, _, _ = routes
    scope = _scope("GET", "/login", cookie="csrf_token=tok")
    status, _, body = await _run(login_get, scope, _FakeReceive(b""))
    assert status == 200
    text = body.decode()
    assert 'name="_csrf"' in text
    assert 'value="tok"' in text


@pytest.mark.asyncio
async def test_login_get_url_encodes_next_in_action(routes) -> None:
    """A `next` containing `&` must be URL-encoded in the form action attribute."""
    login_get, _, _ = routes
    scope = _scope("GET", "/login")
    scope["query_string"] = b"next=/dashboard?x=1%26y=2"
    status, _, body = await _run(login_get, scope, _FakeReceive(b""))
    assert status == 200
    text = body.decode()
    # In the form `action`, special chars must be percent-encoded
    assert "/dashboard%3Fx%3D1%2526y%3D2" in text or "%26" in text
