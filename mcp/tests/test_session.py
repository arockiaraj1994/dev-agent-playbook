"""Tests for session.py — DashboardSession: cookie management and CSRF."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from session import DashboardSession, _build_cookie, _expires_to_max_age, _read_cookie


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------


def test_read_cookie_present() -> None:
    scope = {
        "headers": [(b"cookie", b"session=abc123; other=xyz")]
    }
    assert _read_cookie(scope, "session") == "abc123"


def test_read_cookie_missing() -> None:
    scope = {"headers": [(b"cookie", b"other=xyz")]}
    assert _read_cookie(scope, "session") is None


def test_read_cookie_no_headers() -> None:
    assert _read_cookie({"headers": []}, "session") is None


def test_expires_to_max_age_none() -> None:
    assert _expires_to_max_age(None) is None


def test_expires_to_max_age_future() -> None:
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    age = _expires_to_max_age(future)
    assert age is not None
    assert 86000 < age <= 86401


def test_expires_to_max_age_past_clamped_to_1() -> None:
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    # Past expiry → clamped to 1 (not negative)
    age = _expires_to_max_age(past)
    assert age == 1


def test_build_cookie_attributes() -> None:
    val = _build_cookie("session", "tok", http_only=True, secure=False, max_age=3600)
    assert "session=tok" in val
    assert "HttpOnly" in val
    assert "SameSite=Strict" in val
    assert "Max-Age=3600" in val
    assert "Secure" not in val


def test_build_cookie_secure() -> None:
    val = _build_cookie("session", "tok", http_only=True, secure=True, max_age=None)
    assert "Secure" in val
    assert "Max-Age" not in val


# ---------------------------------------------------------------------------
# DashboardSession — session cookie
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_mgr(tmp_path: Path) -> DashboardSession:
    from auth import AuthStore

    store = AuthStore(tmp_path / "auth.db")
    await store.init()
    return DashboardSession(store)


@pytest.mark.asyncio
async def test_resolve_cookie_valid_session_token(tmp_path: Path) -> None:
    from auth import AuthStore

    store = AuthStore(tmp_path / "auth.db")
    await store.init()
    await store.create_user("alice", "pw", "admin")
    user = await store.verify_login("alice", "pw")
    token_data = await store.create_token(user["id"], None, token_type="session")
    token = token_data["token"]

    session = DashboardSession(store)
    scope = {"headers": [(b"cookie", f"session={token}".encode())]}
    principal = await session.resolve_cookie(scope)
    assert principal is not None
    assert principal.user_name == "alice"
    assert principal.role == "admin"


@pytest.mark.asyncio
async def test_resolve_cookie_mcp_token_rejected(tmp_path: Path) -> None:
    """An MCP token must not be accepted as a session cookie."""
    from auth import AuthStore

    store = AuthStore(tmp_path / "auth.db")
    await store.init()
    await store.create_user("bob", "pw", "user")
    user = await store.verify_login("bob", "pw")
    token_data = await store.create_token(user["id"], None, token_type="mcp")
    token = token_data["token"]

    session = DashboardSession(store)
    scope = {"headers": [(b"cookie", f"session={token}".encode())]}
    assert await session.resolve_cookie(scope) is None


@pytest.mark.asyncio
async def test_resolve_cookie_missing_returns_none(session_mgr: DashboardSession) -> None:
    scope = {"headers": []}
    assert await session_mgr.resolve_cookie(scope) is None


@pytest.mark.asyncio
async def test_resolve_cookie_invalid_token_returns_none(session_mgr: DashboardSession) -> None:
    scope = {"headers": [(b"cookie", b"session=totally-fake-token")]}
    assert await session_mgr.resolve_cookie(scope) is None


def test_session_cookie_header_http_only(session_mgr: DashboardSession) -> None:
    name, value = session_mgr.session_cookie_header("tok123", None, secure=False)
    assert name == b"set-cookie"
    cookie = value.decode()
    assert "session=tok123" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Strict" in cookie


def test_session_cookie_header_with_expiry(session_mgr: DashboardSession) -> None:
    future = (datetime.now(UTC) + timedelta(days=5)).isoformat()
    _, value = session_mgr.session_cookie_header("tok", future, secure=False)
    assert "Max-Age=" in value.decode()


def test_clear_session_cookie_header_zero_max_age(session_mgr: DashboardSession) -> None:
    _, value = session_mgr.clear_session_cookie_header(secure=False)
    assert "Max-Age=0" in value.decode()


# ---------------------------------------------------------------------------
# CSRF
# ---------------------------------------------------------------------------


def test_csrf_generate_is_urlsafe_string(session_mgr: DashboardSession) -> None:
    token = session_mgr.generate_csrf_token()
    assert isinstance(token, str)
    assert len(token) >= 32


def test_csrf_validate_matching(session_mgr: DashboardSession) -> None:
    tok = "some-csrf-token"
    assert session_mgr.validate_csrf(tok, tok) is True


def test_csrf_validate_mismatch(session_mgr: DashboardSession) -> None:
    assert session_mgr.validate_csrf("abc", "xyz") is False


def test_csrf_validate_none_cookie(session_mgr: DashboardSession) -> None:
    assert session_mgr.validate_csrf(None, "xyz") is False


def test_csrf_validate_none_form(session_mgr: DashboardSession) -> None:
    assert session_mgr.validate_csrf("abc", None) is False


def test_csrf_cookie_header_not_http_only(session_mgr: DashboardSession) -> None:
    _, value = session_mgr.csrf_cookie_header("tok", secure=False)
    assert "HttpOnly" not in value.decode()
    assert "SameSite=Strict" in value.decode()


def test_read_csrf_cookie(session_mgr: DashboardSession) -> None:
    scope = {"headers": [(b"cookie", b"csrf_token=mycsrf; session=s")]}
    assert session_mgr.read_csrf_cookie(scope) == "mycsrf"


def test_read_csrf_cookie_missing(session_mgr: DashboardSession) -> None:
    scope = {"headers": []}
    assert session_mgr.read_csrf_cookie(scope) is None
