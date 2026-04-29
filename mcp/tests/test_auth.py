"""Tests for auth.py — AuthStore: users, tokens, password hashing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from auth import AuthStore, _hash_password, _verify_password


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------


def test_hash_and_verify_correct_password() -> None:
    h = _hash_password("secret123")
    assert _verify_password("secret123", h)


def test_verify_wrong_password_fails() -> None:
    h = _hash_password("secret123")
    assert not _verify_password("wrong", h)


def test_hash_is_non_deterministic() -> None:
    assert _hash_password("abc") != _hash_password("abc")


# ---------------------------------------------------------------------------
# AuthStore — users
# ---------------------------------------------------------------------------


@pytest.fixture
async def store(tmp_path: Path) -> AuthStore:
    s = AuthStore(tmp_path / "auth.db")
    await s.init()
    return s


@pytest.mark.asyncio
async def test_seed_default_admin_creates_admin(store: AuthStore) -> None:
    await store.seed_default_admin("admin", "admin")
    users = await store.list_users()
    assert len(users) == 1
    assert users[0]["username"] == "admin"
    assert users[0]["role"] == "admin"


@pytest.mark.asyncio
async def test_seed_skips_when_users_exist(store: AuthStore) -> None:
    await store.seed_default_admin("admin", "admin")
    await store.seed_default_admin("admin2", "admin2")  # should be a no-op
    users = await store.list_users()
    assert len(users) == 1


@pytest.mark.asyncio
async def test_create_user(store: AuthStore) -> None:
    await store.create_user("alice", "pass1", "user")
    users = await store.list_users()
    assert any(u["username"] == "alice" and u["role"] == "user" for u in users)


@pytest.mark.asyncio
async def test_duplicate_username_raises(store: AuthStore) -> None:
    await store.create_user("alice", "pass1", "user")
    with pytest.raises(Exception):
        await store.create_user("alice", "pass2", "user")


@pytest.mark.asyncio
async def test_verify_login_correct(store: AuthStore) -> None:
    await store.create_user("bob", "hunter2", "user")
    result = await store.verify_login("bob", "hunter2")
    assert result is not None
    assert result["username"] == "bob"
    assert result["role"] == "user"


@pytest.mark.asyncio
async def test_verify_login_wrong_password(store: AuthStore) -> None:
    await store.create_user("bob", "hunter2", "user")
    assert await store.verify_login("bob", "wrong") is None


@pytest.mark.asyncio
async def test_verify_login_unknown_user(store: AuthStore) -> None:
    assert await store.verify_login("nobody", "x") is None


# ---------------------------------------------------------------------------
# AuthStore — tokens
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_and_resolve_mcp_token(store: AuthStore) -> None:
    user = await store.create_user("alice", "pw", "user")
    token_data = await store.create_token(user["id"], expires_in_days=None, token_type="mcp")
    assert token_data["expires_at"] is None
    assert token_data["token_type"] == "mcp"
    principal = await store.resolve_token(token_data["token"], token_type="mcp")
    assert principal is not None
    assert principal.user_name == "alice"
    assert principal.role == "user"


@pytest.mark.asyncio
async def test_create_and_resolve_session_token(store: AuthStore) -> None:
    user = await store.create_user("bob", "pw", "admin")
    token_data = await store.create_token(user["id"], expires_in_days=1, token_type="session")
    assert token_data["token_type"] == "session"
    principal = await store.resolve_token(token_data["token"], token_type="session")
    assert principal is not None
    assert principal.user_name == "bob"
    assert principal.role == "admin"


@pytest.mark.asyncio
async def test_mcp_token_not_usable_as_session(store: AuthStore) -> None:
    """MCP token must not resolve when queried as a session token."""
    user = await store.create_user("carol", "pw", "user")
    token_data = await store.create_token(user["id"], expires_in_days=None, token_type="mcp")
    assert await store.resolve_token(token_data["token"], token_type="session") is None


@pytest.mark.asyncio
async def test_session_token_not_usable_as_mcp(store: AuthStore) -> None:
    """Session token must not resolve when queried as an MCP token."""
    user = await store.create_user("dave", "pw", "user")
    token_data = await store.create_token(user["id"], expires_in_days=None, token_type="session")
    assert await store.resolve_token(token_data["token"], token_type="mcp") is None


@pytest.mark.asyncio
async def test_create_token_with_expiry(store: AuthStore) -> None:
    user = await store.create_user("eve", "pw", "admin")
    token_data = await store.create_token(user["id"], expires_in_days=5, token_type="mcp")
    assert token_data["expires_at"] is not None
    exp = datetime.fromisoformat(token_data["expires_at"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    assert exp > datetime.now(UTC)
    assert exp < datetime.now(UTC) + timedelta(days=6)


@pytest.mark.asyncio
async def test_resolve_invalid_token_returns_none(store: AuthStore) -> None:
    assert await store.resolve_token("not-a-real-token", token_type="mcp") is None


@pytest.mark.asyncio
async def test_revoke_token(store: AuthStore) -> None:
    user = await store.create_user("frank", "pw", "user")
    token_data = await store.create_token(user["id"], expires_in_days=None, token_type="mcp")
    token = token_data["token"]
    await store.revoke_token(token)
    assert await store.resolve_token(token, token_type="mcp") is None


@pytest.mark.asyncio
async def test_list_tokens_only_shows_mcp_type(store: AuthStore) -> None:
    """list_tokens must only return mcp tokens, not session tokens."""
    user = await store.create_user("grace", "pw", "user")
    await store.create_token(user["id"], expires_in_days=None, token_type="mcp")
    await store.create_token(user["id"], expires_in_days=1, token_type="mcp")
    await store.create_token(user["id"], expires_in_days=None, token_type="session")
    tokens = await store.list_tokens(user["id"])
    assert len(tokens) == 2
    assert all(t.get("token_type", "mcp") == "mcp" or "token_type" not in t for t in tokens)
    unlimited = next(t for t in tokens if t["expires_at"] is None)
    assert unlimited["active"] is True


@pytest.mark.asyncio
async def test_expired_token_not_resolved(store: AuthStore, monkeypatch) -> None:
    user = await store.create_user("henry", "pw", "user")
    token_data = await store.create_token(user["id"], expires_in_days=1, token_type="mcp")
    token = token_data["token"]

    from datetime import timezone
    import auth as auth_mod

    future = datetime.now(UTC) + timedelta(days=2)

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return future.replace(tzinfo=tz or timezone.utc)

    monkeypatch.setattr(auth_mod, "datetime", FakeDatetime)
    principal = store._resolve_token_sync(token, "mcp")
    assert principal is None
