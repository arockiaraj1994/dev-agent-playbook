"""
server.py — Dev Agent Playbook MCP Server (SSE only; read-only rules + usage metrics).

Tools:
  - list_projects
  - list_rule_docs
  - get_agents_md
  - get_rules
  - get_pattern
  - get_skill
  - search_rules

Run:
  uv run server.py

Transport: HTTP + Server-Sent Events on MCP_PORT (default 3000). Stdio transport
was removed in 0.3.0 — every install is now a centrally hosted server.

Config (optional): config.toml next to server.py, or path in MCP_CONFIG.
  [enable] auth — default false. Same flag governs both /sse and /dashboard.
    When true, Bearer tokens are validated via Keycloak introspection. Set:
      KEYCLOAK_URL, KEYCLOAK_REALM, MCP_CLIENT_ID, MCP_CLIENT_SECRET.

Other env vars:
  MCP_PORT          — SSE / dashboard HTTP port (default 3000).
  MCP_HOST          — bind host (default 127.0.0.1; use 0.0.0.0 for LAN).
  MCP_DB_PATH       — sqlite metrics DB (default <repo>/mcp/data/metrics.db).
  MCP_INACTIVE_DAYS — threshold for "inactive" status (default 2).
  MCP_SNIPPET_SIZE  — search snippet size in chars (default 300, 50–5000).

Rules load from the parent of the mcp/ directory.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import uvicorn
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.sse import SseServerTransport
from mcp.types import (
    ServerCapabilities,
    TextContent,
    Tool,
)
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from starlette.types import Receive, Scope, Send

from dashboard.routes import build_dashboard_routes
from identity import (
    EditorInfo,
    IdentityMiddleware,
    KeycloakConfig,
    Principal,
    editor_var,
    principal_var,
    scope_principal,
)
from loader import RulesStore, bootstrap, resolve_rules_root
from metrics import MetricsStore, summarize_args
from search import RulesSearchEngine
from tools import docs as _docs_mod
from tools import projects as _projects_mod
from tools import search_tool as _search_mod

# ---------------------------------------------------------------------------
# Logging — stderr only (stdout is reserved for protocol output if any)
# ---------------------------------------------------------------------------

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dev-agent-playbook")

SERVER_LABEL = os.getenv("MCP_SERVER_LABEL", "dev-agent-playbook")
SERVER_VERSION = "0.3.0"
DEFAULT_PORT = 3000
DEFAULT_HOST = "127.0.0.1"
DEFAULT_INACTIVE_DAYS = 2
_DEFAULT_DB_REL = Path("data") / "metrics.db"

# ---------------------------------------------------------------------------
# Startup — load rules + index
# ---------------------------------------------------------------------------

logger.info("Bootstrapping rules store...")
try:
    store: RulesStore = bootstrap()
except FileNotFoundError as e:
    logger.error("%s", e)
    sys.exit(1)

if not store.docs:
    root = resolve_rules_root()
    found_subdirs = sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "mcp"
    )
    if found_subdirs:
        hint = (
            "Found these subdirectories under the rules root, but none contained "
            f"loadable .md rules: {found_subdirs}. Each project must contain at "
            "least one markdown file (e.g. agents.md)."
        )
    else:
        hint = (
            "The rules root has no project subdirectories. Expected layout: "
            "<project>/agents.md and related paths next to mcp/."
        )
    logger.error("No markdown rule docs loaded under %s. %s", root, hint)
    sys.exit(1)

engine: RulesSearchEngine = RulesSearchEngine(store)
logger.info("Ready. Projects: %s", store.projects())

# Metrics store is initialized in main() (it needs an event loop). Module-level
# `metrics_store` stays None during import, so unit tests that import the module
# without running main() see no metrics writes.
metrics_store: MetricsStore | None = None
inactive_days: int = DEFAULT_INACTIVE_DAYS

# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

server = Server(SERVER_LABEL)


# ---------------------------------------------------------------------------
# Tool registry — add new tools by creating a module in tools/ and appending
# it to _TOOL_MODULES below.
# ---------------------------------------------------------------------------

_TOOL_MODULES = [_projects_mod, _docs_mod, _search_mod]


@server.list_tools()
async def list_tools() -> list[Tool]:
    defs: list[Tool] = []
    for mod in _TOOL_MODULES:
        defs.extend(mod.DEFINITIONS)
    return defs


# ---------------------------------------------------------------------------
# Tool dispatch — typed inner + metrics-recording wrapper
# ---------------------------------------------------------------------------


@dataclass
class _CallContext:
    """Per-call mutable info collected during dispatch and used for metrics."""

    status: str = "ok"
    query: str | None = None
    doc_path: str | None = None
    top_result_path: str | None = None
    top_result_score: float | None = None


async def _dispatch_typed(
    name: str,
    arguments: dict,
    ctx: _CallContext,
) -> list[TextContent]:
    """Delegate to the owning tool module; mutates `ctx` with metrics info."""
    for mod in _TOOL_MODULES:
        result = await mod.dispatch(name, arguments, ctx, store, engine)
        if result is not None:
            return result
    ctx.status = "error"
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def dispatch_tool(name: str, arguments: dict) -> list[TextContent]:
    """Public tool entrypoint — wraps `_dispatch_typed` and records metrics."""
    args_summary = summarize_args(arguments)
    logger.info("tool=%s args=%s", name, args_summary)
    started = time.monotonic()
    ctx = _CallContext()
    try:
        content = await _dispatch_typed(name, arguments, ctx)
    except Exception as exc:  # noqa: BLE001 — boundary; we record + rethrow
        logger.exception("tool dispatch failed: %s", exc)
        ctx.status = "error"
        latency_ms = int((time.monotonic() - started) * 1000)
        await _record_call(name, args_summary, latency_ms, ctx)
        raise
    latency_ms = int((time.monotonic() - started) * 1000)
    await _record_call(name, args_summary, latency_ms, ctx)
    return content


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    return await dispatch_tool(name, arguments)


async def _record_call(
    name: str,
    args_summary: str,
    latency_ms: int,
    ctx: _CallContext,
) -> None:
    """Persist a call to metrics. Silent no-op when metrics store isn't configured."""
    if metrics_store is None:
        return
    principal = principal_var.get()
    editor = editor_var.get()
    if principal is None:
        # Tool called outside an authenticated request scope (e.g. unit tests).
        return
    try:
        await metrics_store.record_call(
            user_id=principal.user_id,
            user_name=principal.user_name,
            editor_name=editor.name,
            tool_name=name,
            args_summary=args_summary,
            latency_ms=latency_ms,
            status=ctx.status,
            query=ctx.query,
            doc_path=ctx.doc_path,
            top_result_path=ctx.top_result_path,
            top_result_score=ctx.top_result_score,
        )
    except Exception:  # noqa: BLE001 — never let metrics failure break a tool call
        logger.exception("Failed to record call metrics")


# ---------------------------------------------------------------------------
# Editor detection from User-Agent
# ---------------------------------------------------------------------------


_EDITOR_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("claude-code", re.compile(r"claude[-\s]?code", re.IGNORECASE)),
    ("cursor", re.compile(r"cursor", re.IGNORECASE)),
    ("windsurf", re.compile(r"windsurf", re.IGNORECASE)),
    ("zed", re.compile(r"zed", re.IGNORECASE)),
    ("vscode", re.compile(r"vs ?code", re.IGNORECASE)),
]
_VERSION_RE = re.compile(r"(\d+(?:\.\d+){1,3})")


def editor_from_user_agent(ua: str | None) -> EditorInfo:
    """Best-effort editor identification from HTTP User-Agent header."""
    if not ua:
        return EditorInfo(name="unknown", version="")
    for name, pat in _EDITOR_PATTERNS:
        if pat.search(ua):
            v_match = _VERSION_RE.search(ua)
            return EditorInfo(name=name, version=v_match.group(1) if v_match else "")
    first_token = ua.split("/", 1)[0].split()[0] if ua.split("/", 1)[0] else ua
    return EditorInfo(name=first_token.lower() or "unknown", version="")


def _editor_from_scope(scope: Scope) -> EditorInfo:
    headers = scope.get("headers") or []
    custom = next(
        (v.decode("latin-1") for k, v in headers if k.lower() == b"x-mcp-editor"),
        None,
    )
    if custom:
        parts = custom.split("/", 1)
        return EditorInfo(
            name=parts[0].strip().lower() or "unknown",
            version=parts[1].strip() if len(parts) > 1 else "",
        )
    ua = next(
        (v.decode("latin-1") for k, v in headers if k.lower() == b"user-agent"),
        None,
    )
    return editor_from_user_agent(ua)


# ---------------------------------------------------------------------------
# Config (config.toml) and runtime app builder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class McpConfig:
    auth_enabled: bool = False
    keycloak: KeycloakConfig | None = None


def _default_config_path() -> Path:
    return Path(__file__).resolve().parent / "config.toml"


def _load_keycloak_env() -> KeycloakConfig:
    required = ("KEYCLOAK_URL", "KEYCLOAK_REALM", "MCP_CLIENT_ID", "MCP_CLIENT_SECRET")
    values: dict[str, str] = {}
    missing: list[str] = []
    for name in required:
        raw = os.environ.get(name, "").strip()
        if not raw:
            missing.append(name)
        values[name] = raw
    if missing:
        logger.error(
            "auth.enabled=true requires non-empty %s. Set these env vars and "
            "restart, or set [enable].auth=false in config.toml.",
            ", ".join(missing),
        )
        sys.exit(1)
    base = values["KEYCLOAK_URL"].rstrip("/")
    realm = values["KEYCLOAK_REALM"]
    return KeycloakConfig(
        introspect_url=f"{base}/realms/{realm}/protocol/openid-connect/token/introspect",
        client_id=values["MCP_CLIENT_ID"],
        client_secret=values["MCP_CLIENT_SECRET"],
    )


def load_mcp_config() -> McpConfig:
    """Load MCP config from MCP_CONFIG or mcp/config.toml."""
    raw = os.environ.get("MCP_CONFIG", "").strip()
    path = Path(raw).expanduser().resolve() if raw else _default_config_path()
    if not path.is_file():
        return McpConfig(auth_enabled=False)
    try:
        with path.open("rb") as f:
            data = tomllib.load(f)
    except OSError as exc:
        logger.error("Could not read MCP config %s: %s", path, exc)
        sys.exit(1)
    except tomllib.TOMLDecodeError as exc:
        logger.error("Invalid TOML in MCP config %s: %s", path, exc)
        sys.exit(1)

    enable = data.get("enable") or {}
    if not isinstance(enable, dict):
        logger.error("MCP config %s: [enable] must be a table", path)
        sys.exit(1)
    auth_enabled = bool(enable.get("auth", False))
    keycloak = _load_keycloak_env() if auth_enabled else None
    return McpConfig(auth_enabled=auth_enabled, keycloak=keycloak)


def _initialization_options() -> InitializationOptions:
    return InitializationOptions(
        server_name=SERVER_LABEL,
        server_version=SERVER_VERSION,
        capabilities=ServerCapabilities(tools={}),
    )


# ---------------------------------------------------------------------------
# App builder (used by main and tests)
# ---------------------------------------------------------------------------


@dataclass
class AppDeps:
    """Runtime collaborators wired into the Starlette app."""

    cfg: McpConfig
    metrics: MetricsStore
    inactive_days: int
    http_client: httpx.AsyncClient | None = None
    sse_transport: SseServerTransport | None = field(default=None)


def build_app(deps: AppDeps) -> Starlette:
    """Construct the Starlette app: identity middleware + SSE + dashboard."""
    global metrics_store, inactive_days
    metrics_store = deps.metrics
    inactive_days = deps.inactive_days

    sse = deps.sse_transport or SseServerTransport("/messages/")
    deps.sse_transport = sse

    async def mcp_sse_asgi(scope: Scope, receive: Receive, send: Send) -> None:
        principal: Principal | None = scope_principal(scope)
        editor = _editor_from_scope(scope)

        p_token = principal_var.set(principal)
        e_token = editor_var.set(editor)
        try:
            if metrics_store is not None and principal is not None:
                try:
                    await metrics_store.upsert_registration(
                        user_id=principal.user_id,
                        user_name=principal.user_name,
                        editor_name=editor.name,
                        editor_version=editor.version,
                    )
                except Exception:
                    logger.exception("upsert_registration failed")
            async with sse.connect_sse(scope, receive, send) as streams:
                await server.run(streams[0], streams[1], _initialization_options())
        finally:
            principal_var.reset(p_token)
            editor_var.reset(e_token)

    async def sse_endpoint(request: Request) -> Response:
        await mcp_sse_asgi(request.scope, request.receive, request._send)  # noqa: SLF001
        return Response()

    routes = [
        Route("/sse", endpoint=sse_endpoint, methods=["GET"]),
        Mount("/messages/", app=sse.handle_post_message),
        Mount(
            "/dashboard",
            routes=build_dashboard_routes(deps.metrics, deps.inactive_days, SERVER_LABEL),
        ),
        Route("/healthz", endpoint=_healthz, methods=["GET"]),
    ]

    app = Starlette(routes=routes)
    app.add_middleware(
        IdentityMiddleware,
        auth_enabled=deps.cfg.auth_enabled,
        keycloak=deps.cfg.keycloak,
        http_client=deps.http_client,
    )
    return app


async def _healthz(_request: Request) -> Response:
    return Response("ok", media_type="text/plain")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _resolve_db_path() -> Path:
    raw = os.environ.get("MCP_DB_PATH", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parent / _DEFAULT_DB_REL


def _resolve_inactive_days() -> int:
    raw = os.environ.get("MCP_INACTIVE_DAYS", "").strip()
    if not raw:
        return DEFAULT_INACTIVE_DAYS
    try:
        v = int(raw)
        if v < 1:
            logger.warning("MCP_INACTIVE_DAYS=%s < 1; clamping to 1.", raw)
            return 1
        return v
    except ValueError:
        logger.warning("MCP_INACTIVE_DAYS=%r not an integer; using default.", raw)
        return DEFAULT_INACTIVE_DAYS


async def _serve() -> None:
    cfg = load_mcp_config()
    port = _int_env("MCP_PORT", DEFAULT_PORT)
    host = os.environ.get("MCP_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST

    metrics = MetricsStore(_resolve_db_path())
    await metrics.init()

    days = _resolve_inactive_days()

    timeout = httpx.Timeout(15.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as http_client:
        app = build_app(
            AppDeps(
                cfg=cfg,
                metrics=metrics,
                inactive_days=days,
                http_client=http_client,
            )
        )
        logger.info(
            "Starting on http://%s:%d (auth=%s, inactive_days=%d, db=%s)",
            host,
            port,
            cfg.auth_enabled,
            days,
            metrics.path,
        )
        config = uvicorn.Config(app, host=host, port=port, log_level="info")
        await uvicorn.Server(config).serve()


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.error("%s must be an integer, got %r", name, raw)
        sys.exit(1)


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
