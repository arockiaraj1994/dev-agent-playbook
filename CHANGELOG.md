# Changelog

All notable changes to this repo are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
The MCP server (under `mcp/`) follows [Semantic Versioning](https://semver.org/).
Tool name or schema changes bump the **minor** version (until 1.0.0); breaking
changes after 1.0.0 will bump the **major**.

## [Unreleased]

## [0.3.0]

### Added
- **Usage dashboard** at `/dashboard/` (Starlette + Jinja2). Shows users / adoption, tool popularity + latency, search query log + zero-result queries, recent activity feed, and per-user drill-downs. Same `auth.enabled` flag gates both `/sse` and `/dashboard`.
- SQLite-backed metrics: every MCP tool call and every (user, editor) registration is recorded. New tables: `registrations`, `calls`. Database path configurable via `MCP_DB_PATH` (default `mcp/data/metrics.db`); excluded from git.
- Identity middleware (`identity.py`): when `auth.enabled=true`, validates Keycloak Bearer tokens and uses `preferred_username`. When `auth.enabled=false`, identifies callers via advisory `X-MCP-User` header (or `?user=` query param), falling back to client IP.
- New env vars: `MCP_HOST` (default `127.0.0.1`), `MCP_DB_PATH`, `MCP_INACTIVE_DAYS` (default 2 — threshold for "inactive" status).
- `GET /healthz` liveness probe.
- Editor detection from User-Agent (Claude Code, Cursor, Windsurf, Zed, VS Code).
- New tests: `test_metrics.py`, `test_identity.py`, `test_dashboard.py` (~50 new tests).

### Changed
- **Breaking: stdio transport removed.** The server is now SSE-only. Each install is a centrally hosted HTTP service that editors connect to.
- `setup-claude-code.sh` now takes an SSE URL argument and registers via `claude mcp add --transport sse`. Optional `BATON_RULES_TOKEN` env var adds `Authorization: Bearer …`.
- MCP server version bumped from `0.2.0` to `0.3.0`.
- New runtime dependency: `jinja2` (for dashboard templates). Already-required `starlette`/`uvicorn`/`httpx` now also serve the dashboard.
- `mcp/README.md` and root `README.md` rewritten for the hosted-server model.

### Removed
- `mcp_sse_asgi`'s old `KeycloakBearerAuthMiddleware` was extracted and generalized into `identity.IdentityMiddleware`.

### Added
- Root `README.md` with quickstart, repo layout, troubleshooting.
- `CONTRIBUTING.md` — author guide, pattern-vs-skill rule, naming conventions.
- `TEMPLATE.md` — copy-pasteable templates for `agents.md`, patterns, and skills.
- `LICENSE` (Apache 2.0), `.gitignore`, `.editorconfig`.
- `scripts/setup-claude-code.sh` — auto-detects absolute paths and registers the MCP server.
- `scripts/validate-rules.py` — pre-commit/CI gate for rule docs.
- `.pre-commit-config.yaml` and `.github/workflows/ci.yml` (lint + validate + test).
- `mcp/tests/` — unit tests for loader, search, and server tool handlers.
- MCP server: `list_rule_docs(project, doc_type?)` tool — agents can now discover patterns/skills without reading them.
- MCP server: `get_skill(project, skill)` tool — symmetric with `get_pattern`.
- MCP server: optional YAML frontmatter on rule docs (`title`, `description`, `tags`, `applies_to`); used to weight BM25 ranking.
- MCP server: snippets are now annotated with their parent markdown heading.
- MCP server: every tool invocation is logged at INFO with name + arguments.
- MCP server: `MCP_SNIPPET_SIZE` env var to tune snippet size.
- `baton-sso-config/`: stub `architecture.md`, `error-conventions.md`, `anti-patterns.md`, `glossary.md`, `skills/` dir.

### Changed
- MCP server version bumped from `0.1.0` to `0.2.0`.
- BM25 index now weights H1/H2/H3 headings and frontmatter `title`/`tags` 2× over body text.
- `search_rules` default `top_k` raised from 5 to 10; bounds now enforced (1–50).
- Better startup error message when no rule docs are loaded — lists the directories that *were* found.
- "Project not found" errors no longer dump the full project list inline; suggest `list_projects` instead.
- `mcp/pyproject.toml` declares `uvicorn`, `starlette`, `sse-starlette` explicitly (no longer relying on `mcp[cli]` transitive deps).
- `mcp/README.md` no longer claims "no environment variables" — env vars are now documented in a table.

### Removed
- **Breaking:** `get_error_conventions` MCP tool — use `get_rules(project, context="error-conventions")` instead. Agents that hardcoded the old name will need to update.

### Fixed
- Loader now warns (instead of silently skipping) when a markdown file lands in `doc_type="other"` or sits at the repo root outside any `<project>/` dir.
- Cursor config example removed unnecessary `cwd` field; the server resolves paths from `__file__`.
