"""
dashboard/routes.py — Starlette routes for the metrics UI.

Sections:
  /dashboard/                — users + adoption overview
  /dashboard/tools           — tool popularity, latency, rule docs fetched
  /dashboard/searches        — search query log + zero-result queries
  /dashboard/activity        — recent calls (last 100)
  /dashboard/users/{name}    — per-user drill-down
  /dashboard/static/...      — CSS

Authentication is handled at the app level by `IdentityMiddleware`. When
`auth.enabled` is true the middleware rejects unauthenticated requests with
401 before they ever reach these handlers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.routing import BaseRoute, Mount, Route
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from identity import scope_principal
from metrics import MetricsStore

_DASHBOARD_DIR = Path(__file__).resolve().parent
_TEMPLATES_DIR = _DASHBOARD_DIR / "templates"
_STATIC_DIR = _DASHBOARD_DIR / "static"


def _build_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    templates.env.filters["since"] = _since_filter
    templates.env.filters["short_dt"] = _short_dt_filter
    return templates


# ---------------------------------------------------------------------------
# Jinja filters
# ---------------------------------------------------------------------------


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _since_filter(value: str | None) -> str:
    """Turn an ISO timestamp into a coarse 'X ago' string."""
    dt = _parse_iso(value)
    if dt is None:
        return "—"
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _short_dt_filter(value: str | None) -> str:
    dt = _parse_iso(value)
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------
# Route factory
# ---------------------------------------------------------------------------


def build_dashboard_routes(
    store: MetricsStore,
    inactive_days: int,
    server_label: str = "dev-agent-playbook",
) -> list[BaseRoute]:
    """
    Build Starlette routes for /dashboard/*.

    `store` and `inactive_days` are captured by closure so each request gets
    the same backend. Routes are stateless beyond that.
    """
    templates = _build_templates()

    def _ctx(request: Request, **extra: object) -> dict:
        principal = scope_principal(request.scope)
        return {
            "request": request,
            "principal": principal,
            "inactive_days": inactive_days,
            "server_label": server_label,
            "nav": [
                ("Users", "/dashboard/"),
                ("Tools", "/dashboard/tools"),
                ("Searches", "/dashboard/searches"),
                ("Activity", "/dashboard/activity"),
                ("Setup", "/dashboard/setup"),
            ],
            **extra,
        }

    async def dashboard_view(request: Request) -> Response:
        import json as _json
        summary = await store.dashboard_summary(inactive_days=inactive_days)
        calls = await store.list_recent_calls(limit=8)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            _ctx(
                request,
                summary=summary,
                calls=calls,
                hourly_json=_json.dumps(summary.hourly),
                daily_json=_json.dumps(summary.daily),
                page="dashboard",
            ),
        )

    async def users_view(request: Request) -> Response:
        users = await store.list_users(inactive_days=inactive_days)
        summary = await store.adoption_summary(inactive_days=inactive_days)
        return templates.TemplateResponse(
            request,
            "users.html",
            _ctx(request, users=users, summary=summary, page="users"),
        )

    async def tools_view(request: Request) -> Response:
        window_days = _int_query(request, "days", default=7, lo=1, hi=90)
        tool_stats = await store.list_tool_stats(window_days=window_days)
        doc_fetches = await store.list_doc_fetches(window_days=window_days, limit=50)
        return templates.TemplateResponse(
            request,
            "tools.html",
            _ctx(
                request,
                tool_stats=tool_stats,
                doc_fetches=doc_fetches,
                window_days=window_days,
                page="tools",
            ),
        )

    async def searches_view(request: Request) -> Response:
        recent = await store.list_searches(limit=50)
        zero_result = await store.list_zero_result_searches(limit=25)
        return templates.TemplateResponse(
            request,
            "searches.html",
            _ctx(
                request,
                recent_searches=recent,
                zero_result_searches=zero_result,
                page="searches",
            ),
        )

    async def activity_view(request: Request) -> Response:
        calls = await store.list_recent_calls(limit=100)
        return templates.TemplateResponse(
            request,
            "activity.html",
            _ctx(request, calls=calls, page="activity"),
        )

    async def user_detail_view(request: Request) -> Response:
        name = request.path_params["name"]
        detail = await store.get_user(user_name=name, inactive_days=inactive_days)
        if detail is None:
            return HTMLResponse(
                f"<p>User <code>{_html_escape(name)}</code> not found.</p>",
                status_code=404,
            )
        return templates.TemplateResponse(
            request,
            "user_detail.html",
            _ctx(request, detail=detail, page="users"),
        )

    async def setup_view(request: Request) -> Response:
        base = str(request.base_url).rstrip("/")
        sse_url = f"{base}/sse"
        return templates.TemplateResponse(
            request,
            "setup.html",
            _ctx(request, sse_url=sse_url, page="setup"),
        )

    static = Mount(
        "/static",
        app=StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )

    return [
        Route("/", endpoint=dashboard_view, methods=["GET"]),
        Route("/users", endpoint=users_view, methods=["GET"]),
        Route("/tools", endpoint=tools_view, methods=["GET"]),
        Route("/searches", endpoint=searches_view, methods=["GET"]),
        Route("/activity", endpoint=activity_view, methods=["GET"]),
        Route("/setup", endpoint=setup_view, methods=["GET"]),
        Route("/users/{name}", endpoint=user_detail_view, methods=["GET"]),
        static,
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _int_query(request: Request, key: str, *, default: int, lo: int, hi: int) -> int:
    raw = request.query_params.get(key)
    if raw is None:
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    return max(lo, min(hi, v))


def _html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
