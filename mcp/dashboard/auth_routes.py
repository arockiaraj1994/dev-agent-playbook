"""
dashboard/auth_routes.py — Browser login / logout for the dashboard.

Routes (registered in server.py):
  GET  /login   — render login form (redirect to /dashboard/ if already logged in)
  POST /login   — validate credentials, set session cookie, redirect
  POST /logout  — revoke session token, clear cookie, redirect to /login

These routes are PUBLIC (no auth required before reaching them) so that
unauthenticated users can log in. POST /login and POST /logout both validate
the double-submit CSRF token (cookie set on GET /login by AppAuthMiddleware).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import quote

from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.templating import Jinja2Templates

if TYPE_CHECKING:
    from auth import AuthStore
    from session import DashboardSession

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

def _safe_next(next_url: str | None) -> str:
    """Validate the ?next= redirect target to prevent open-redirect attacks."""
    if not next_url:
        return "/dashboard/"
    # Only allow relative paths starting with / but not //
    if not next_url.startswith("/") or next_url.startswith("//"):
        return "/dashboard/"
    return next_url


def _is_secure(request: Request) -> bool:
    return request.url.scheme == "https"


def build_auth_routes(
    auth_store: "AuthStore",
    session: "DashboardSession",
    server_label: str,
) -> tuple:
    """Return (login_get, login_post, logout_post) handlers."""

    def _form_csrf_valid(request: Request, form) -> bool:
        cookie_val = session.read_csrf_cookie(request.scope)
        form_val = str(form.get("_csrf", ""))
        return session.validate_csrf(cookie_val, form_val)

    def _csrf_for_template(request: Request) -> str:
        existing = session.read_csrf_cookie(request.scope)
        if existing:
            return existing
        # AppAuthMiddleware stashes a freshly-generated token here on GET /login
        fresh = (request.scope.get("state") or {}).get("_fresh_csrf")
        return fresh or ""

    async def login_get(request: Request) -> Response:
        # If already authenticated, skip the login page
        existing = _read_session_token(request)
        if existing:
            principal = await auth_store.resolve_token(existing, token_type="session")
            if principal is not None:
                return _redirect("/dashboard/")

        next_url = request.query_params.get("next", "")
        error = request.query_params.get("error", "")
        return _render_login(
            request,
            server_label=server_label,
            next_url=next_url,
            error=error,
            csrf_token=_csrf_for_template(request),
        )

    async def login_post(request: Request) -> Response:
        form = await request.form()

        if not _form_csrf_valid(request, form):
            return _render_login(
                request,
                server_label=server_label,
                next_url=str(form.get("next", "")),
                error="Session expired. Please try again.",
                csrf_token=_csrf_for_template(request),
                status_code=403,
            )

        username = str(form.get("username", "")).strip()
        password = str(form.get("password", "")).strip()

        if not username or not password:
            return _render_login(
                request,
                server_label=server_label,
                next_url=str(form.get("next", "")),
                error="Username and password are required.",
                csrf_token=_csrf_for_template(request),
            )

        user = await auth_store.verify_login(username, password)
        if user is None:
            return _render_login(
                request,
                server_label=server_label,
                next_url=str(form.get("next", "")),
                error="Invalid username or password.",
                csrf_token=_csrf_for_template(request),
            )

        # Session tokens have no DB-level expiry; the idle window is managed
        # entirely by the sliding Max-Age on the cookie. Use the same sliding
        # window from the start so the cookie's lifetime is consistent across
        # the very first response and every subsequent one.
        token_data = await auth_store.create_token(
            user["id"], None, token_type="session"
        )
        secure = _is_secure(request)
        next_url = _safe_next(str(form.get("next", "")))

        response = _redirect(next_url)
        response.raw_headers.append(
            session.refresh_cookie_header(token_data["token"], secure=secure)
        )
        return response

    async def logout_post(request: Request) -> Response:
        form = await request.form()
        if not _form_csrf_valid(request, form):
            return HTMLResponse(
                "403 Forbidden — invalid CSRF token.", status_code=403
            )

        token = _read_session_token(request)
        if token:
            await auth_store.revoke_token(token)

        secure = _is_secure(request)
        response = _redirect("/login")
        response.raw_headers.append(session.clear_session_cookie_header(secure=secure))
        return response

    return login_get, login_post, logout_post


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_session_token(request: Request) -> str | None:
    return request.cookies.get("session")


def _redirect(url: str) -> Response:
    from starlette.responses import Response as _R

    return _R(
        status_code=303,
        headers={"location": url},
    )


def _render_login(
    request: Request,
    *,
    server_label: str,
    next_url: str,
    error: str,
    csrf_token: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    # `next_url` is interpolated into the form action's query string and into
    # a hidden input. The hidden input is HTML-escape-safe; the action
    # additionally needs URL-encoding so `&`, `#`, `?` etc. don't corrupt the URL.
    next_url_query = quote(next_url, safe="/") if next_url else ""
    return HTMLResponse(
        _templates.get_template("login.html").render(
            {
                "request": request,
                "server_label": server_label,
                "next_url": next_url,
                "next_url_query": next_url_query,
                "error": error,
                "csrf_token": csrf_token,
            }
        ),
        status_code=status_code,
    )
