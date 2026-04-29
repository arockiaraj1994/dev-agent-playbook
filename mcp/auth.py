"""
auth.py — In-built authentication store: users, roles, and opaque tokens.

Schema (in the same SQLite DB as metrics):
  users(id, username, password_hash, role, created_at)
  tokens(token, user_id, token_type, expires_at NULLABLE, created_at)

Roles: "admin" | "user"
Token types: "mcp" (Bearer for editors) | "session" (HttpOnly cookie for dashboard)
Tokens: secrets.token_urlsafe(32) — no expiry unless expires_in_days is set.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from identity import Principal

_HASH_ITERATIONS = 260_000


# ---------------------------------------------------------------------------
# Password hashing (stdlib only — pbkdf2-sha256 + random salt)
# ---------------------------------------------------------------------------


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _HASH_ITERATIONS)
    return f"pbkdf2:sha256:{salt.hex()}:{dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        _, algo, salt_hex, hash_hex = stored.split(":")
    except ValueError:
        return False
    if algo != "sha256":
        return False
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _HASH_ITERATIONS)
    return secrets.compare_digest(dk.hex(), hash_hex)


# ---------------------------------------------------------------------------
# AuthStore
# ---------------------------------------------------------------------------


class AuthStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # -- Lifecycle -----------------------------------------------------------

    async def init(self) -> None:
        await asyncio.to_thread(self._init_sync)

    def _init_sync(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tokens (
                    token TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    expires_at TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_tokens_user ON tokens(user_id);
            """)
            # Migrate: add token_type column if it doesn't exist yet
            existing = {row[1] for row in conn.execute("PRAGMA table_info(tokens)").fetchall()}
            if "token_type" not in existing:
                conn.execute(
                    "ALTER TABLE tokens ADD COLUMN token_type TEXT NOT NULL DEFAULT 'mcp'"
                )

    async def seed_default_admin(self, username: str, password: str) -> None:
        """Insert the default admin only when the users table is empty."""
        await asyncio.to_thread(self._seed_sync, username, password)

    def _seed_sync(self, username: str, password: str) -> None:
        with self._connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0:
                return
            conn.execute(
                "INSERT INTO users(id, username, password_hash, role, created_at) VALUES(?,?,?,?,?)",
                (
                    secrets.token_hex(16),
                    username,
                    _hash_password(password),
                    "admin",
                    datetime.now(UTC).isoformat(),
                ),
            )

    # -- Users ---------------------------------------------------------------

    async def create_user(self, username: str, password: str, role: str) -> dict:
        return await asyncio.to_thread(self._create_user_sync, username, password, role)

    def _create_user_sync(self, username: str, password: str, role: str) -> dict:
        user_id = secrets.token_hex(16)
        now = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO users(id, username, password_hash, role, created_at) VALUES(?,?,?,?,?)",
                (user_id, username, _hash_password(password), role, now),
            )
        return {"id": user_id, "username": username, "role": role, "created_at": now}

    async def verify_login(self, username: str, password: str) -> dict | None:
        return await asyncio.to_thread(self._verify_login_sync, username, password)

    def _verify_login_sync(self, username: str, password: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, username, password_hash, role FROM users WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            return None
        if not _verify_password(password, row["password_hash"]):
            return None
        return {"id": row["id"], "username": row["username"], "role": row["role"]}

    async def list_users(self) -> list[dict]:
        return await asyncio.to_thread(self._list_users_sync)

    def _list_users_sync(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, username, role, created_at FROM users ORDER BY created_at"
            ).fetchall()
        return [dict(r) for r in rows]

    # -- Tokens --------------------------------------------------------------

    async def create_token(
        self,
        user_id: str,
        expires_in_days: int | None,
        token_type: str = "mcp",
    ) -> dict:
        return await asyncio.to_thread(
            self._create_token_sync, user_id, expires_in_days, token_type
        )

    def _create_token_sync(
        self, user_id: str, expires_in_days: int | None, token_type: str
    ) -> dict:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        expires_at = (
            (now + timedelta(days=expires_in_days)).isoformat()
            if expires_in_days is not None
            else None
        )
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO tokens(token, user_id, token_type, expires_at, created_at) VALUES(?,?,?,?,?)",
                (token, user_id, token_type, expires_at, now.isoformat()),
            )
        return {"token": token, "expires_at": expires_at, "token_type": token_type}

    async def resolve_token(self, token: str, token_type: str = "mcp") -> Principal | None:
        return await asyncio.to_thread(self._resolve_token_sync, token, token_type)

    def _resolve_token_sync(self, token: str, token_type: str) -> Principal | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT u.id, u.username, u.role, t.expires_at
                FROM tokens t JOIN users u ON t.user_id = u.id
                WHERE t.token = ? AND t.token_type = ?
                """,
                (token, token_type),
            ).fetchone()
        if row is None:
            return None
        if row["expires_at"] is not None:
            exp = datetime.fromisoformat(row["expires_at"])
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=UTC)
            if datetime.now(UTC) > exp:
                return None
        return Principal(user_id=row["id"], user_name=row["username"], role=row["role"])

    async def list_tokens(self, user_id: str) -> list[dict]:
        """Return only mcp-type tokens (shown in the /dashboard/tokens page)."""
        return await asyncio.to_thread(self._list_tokens_sync, user_id)

    def _list_tokens_sync(self, user_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT token, expires_at, created_at FROM tokens
                WHERE user_id = ? AND token_type = 'mcp'
                ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        now = datetime.now(UTC)
        result = []
        for r in rows:
            expires_at = r["expires_at"]
            if expires_at is not None:
                exp = datetime.fromisoformat(expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=UTC)
                active = now <= exp
            else:
                active = True
            result.append(
                {
                    "token": r["token"],
                    "expires_at": expires_at,
                    "created_at": r["created_at"],
                    "active": active,
                }
            )
        return result

    async def revoke_token(self, token: str) -> None:
        await asyncio.to_thread(self._revoke_token_sync, token)

    def _revoke_token_sync(self, token: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tokens WHERE token = ?", (token,))
