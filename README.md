# dev-agent-playbook

## Why this project?

Building apps from scratch is relatively easy with AI tools. The harder problem is **making changes in a large, active codebase** — adding features, fixing bugs, or refactoring across a team where everyone uses a different AI editor.

In an enterprise project, many developers contribute simultaneously, each with their own preferred AI tool: some use Cursor, some use Claude Code, some use Windsurf. The challenge is: how do you produce consistent, high-quality code regardless of which tool a developer is using?

Common solutions like `AGENTS.md` or `DESIGN.md` work, but they require you to dump **all** your project context into a single file upfront — context that isn't relevant to every task, every time. That overhead grows with the project.

**This project solves that with on-demand context delivery over MCP.** Instead of front-loading everything, your rule docs, architecture decisions, error conventions, patterns, and skills live on a central server. Every AI editor — regardless of vendor — connects to it and retrieves only the context relevant to the current task, via BM25 search and structured fetch tools. The server records every tool call so you can see exactly which rules are being used (and which gaps need filling).

<div align="center">
  <img src="docs/screenshots/dev_p_dashboard.png" alt="Dashboard" width="49%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <img src="docs/screenshots/dev_p_projects.png" alt="Projects" width="49%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
</div>

---

## Who is this for?

### Rule & skill definers — senior developers and tech managers

You own the standards. Your job is to write and maintain the rule docs that keep AI-generated code consistent across the team. You add new projects, define patterns, document error conventions, and write skills for common tasks. The dashboard shows you which rules are actually being used and where the gaps are.

→ Start with [Adding a project](#adding-a-project)

### Consumers — developers writing code with AI tools

You connect your editor once and then work normally. Instead of copy-pasting context or maintaining local AGENTS.md files, you ask your AI editor a task-focused question and it pulls the right rules automatically. The server handles context retrieval.

→ Start with [Using it in your editor](#using-it-in-your-editor)

---

## Start the server

> This is done once by the team — typically by whoever runs shared infrastructure.

```bash
git clone <this-repo>
cd <repo>/mcp
uv sync
uv run dev.py            # regen INDEX.md → validate → start the server
```

`uv run dev.py` is the recommended dev-loop entry point. It regenerates
each project's `INDEX.md`, runs the validator (`scripts/validate-rules.py
--check`), and only starts the server if validation passes. Add
`--no-serve` to use it as a pre-commit hook, `--no-regen` to mirror CI
exactly, or `--no-check` to skip validation in a pinch.

If you only want to start the server (skipping the regen + validate
steps):

```bash
uv run server.py
```

To bind on all interfaces (LAN / Docker):

```bash
MCP_HOST=0.0.0.0 MCP_PORT=3000 uv run dev.py
```

**Requirements:** Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

Once started, open the dashboard at **`http://localhost:3000/dashboard/`** — it shows connected editors, call activity, and which rules are being used. Editor connection instructions are in the dashboard under **Setup**.

---

## Adding a project

A project is a directory next to `mcp/` that holds rule docs for one codebase or domain. The server loads all projects at startup.

### Step 1 — Create the project directory

```
<your-project>/
  README.md                          ← humans
  AGENTS.md                          ← AI entry point (required)
  INDEX.md                           ← auto-generated trigger map (do not hand-edit)
  core/
    guardrails.md                    ← always-on MUST / MUST NOT
    definition-of-done.md            ← tests + lint + security gates
    glossary.md                      ← domain terms
  architecture/
    overview.md                      ← system overview
    decisions/                       ← ADRs, one .md per decision
    diagrams/                        ← optional images
  languages/
    <lang>/                          ← java | typescript | python | kotlin | sql | shell-yaml
      standards.md
      testing.md
      anti-patterns.md
  patterns/
    <name>.md                        ← canonical noun-named patterns
  skills/
    <action>.md                      ← verb-noun playbooks
  workflows/
    new-feature.md
    bug-fix.md
    security-fix.md
    refactor.md
  gates/
    README.md                        ← what each gate enforces
    scripts/
      verify-<lang>.sh               ← executable verification (lint + tests + security)
```

Use `TEMPLATE.md` for copy-pasteable starters and look at `apache-camel/`,
`baton-sso-config/`, or `integration-manager/` for live examples.

### Step 2 — Write `AGENTS.md` first

This is the identity doc — what role the AI plays in this project. Keep it
focused: every line should earn its place. Cross-cutting MUST/MUST NOT
rules belong in `core/guardrails.md`, not here.

### Step 3 — Author the always-on docs

| File | What goes in it |
|------|----------------|
| `core/guardrails.md` | Hard MUST / MUST NOT rules. Loaded on every task via `get_guardrails`. |
| `core/definition-of-done.md` | Mechanical (gate scripts) + functional + security checks. |
| `core/glossary.md` | Domain terms so the agent uses your vocabulary. |
| `architecture/overview.md` | Module map, service boundaries, tech stack, external integrations. |

### Step 4 — Languages, patterns, skills, workflows, gates

- `languages/<lang>/standards.md` + `testing.md` + `anti-patterns.md` for each language the project actually uses.
- `patterns/<name>.md` — canonical noun-named patterns ("what good looks like").
- `skills/<action>.md` — verb-noun playbooks. Add `triggers:` and `see_also:` frontmatter so they show up correctly in `INDEX.md`.
- `workflows/{new-feature,bug-fix,security-fix,refactor}.md` — task-driven flows. These are the agent's first stop after `start_task`.
- `gates/README.md` + `gates/scripts/verify-<lang>.sh` (executable). The validator fails if a gate script is not executable.

### Step 5 — Regenerate `INDEX.md` and validate

```bash
python scripts/validate-rules.py --regen-index
python scripts/validate-rules.py --check
```

`--check` fails if any required file is missing, any doc lands in the
`other` bucket, or `INDEX.md` is stale.

### Step 6 — Restart the server

The server loads files once at startup. After adding or editing docs, restart it so changes are visible:

```bash
cd mcp && uv run server.py
```

### Tips for writing good rules

- **Anti-patterns before patterns** — agents that know what NOT to do make fewer bad choices.
- **Be specific, not general** — "don't use Java DSL" beats "follow best practices."
- **Use your actual vocabulary** — if your team says "connector," write "connector," not "endpoint."
- **Start small** — `agents.md` + one or two patterns is enough to see value. Add more as gaps appear in the dashboard's zero-result searches.
- **Check the dashboard** — the Searches page shows queries that returned no results. Those are your next docs to write.

---

## Using it in your editor

> Connect once. The dashboard **Setup** page has the exact config snippet for your editor (Claude Code, Cursor, Windsurf).

Once connected, type task-focused prompts — the agent fetches the right rules automatically.

### How agents use the server

The MCP surface is designed so an agent can orient itself in **one** call
and chain forward from there. The contract:

| Tool | When to call |
|---|---|
| `start_task(project, task)` | **First call for any task.** Returns guardrails + the matched workflow + `Next Calls` pointing at the skills/patterns to fetch next. |
| `get_guardrails(project)` | Re-read always-on rules mid-task. |
| `get_index(project)` | Browse the trigger map without committing to a task. |
| `get_agents_md(project)` | Identity / behavior doc. |
| `get_architecture(project, name?)` | System overview, or a specific ADR. |
| `get_language_rules(project, language, doc?)` | Language standards / testing / anti-patterns. |
| `get_pattern(project, pattern)` | Canonical code pattern. |
| `get_skill(project, skill)` | Verb-noun playbook. |
| `get_workflow(project, name)` | One of `new-feature`, `bug-fix`, `security-fix`, `refactor`. |
| `get_gate(project, name?)` | Gate README + script listing; or metadata for a specific `verify-*.sh`. |
| `search_rules(query, …)` | BM25 fallback when nothing else matches. |
| `list_projects()` / `list_rule_docs(project, doc_type?)` | Discovery. |

### Sample prompts

```
Add a new SFTP inbound route for payments to the apache-camel project.
I need to fix a bug where the orders route is dropping messages.
We have a CVE on Quarkus in integration-manager — patch it.
Refactor the invoice processor without changing behavior.
```

The agent will call `start_task` first, then chain through the next calls
the bundle returns.

---

## The dashboard

`http://<host>:3000/dashboard/` — open this to monitor usage and manage the server.

<div align="center">
  <img src="docs/screenshots/dev_p_dashboard.png" alt="Dashboard — live KPIs, tool call chart, recent activity" width="100%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <sub>Dashboard — connected editors, calls today, zero-result rate, hourly activity</sub>
</div>

<br>

- **Dashboard** — live KPIs: connected editors, calls today, zero-result rate, hourly activity.

<div align="center">
  <img src="docs/screenshots/dev_p_projects.png" alt="Projects — rule health per project" width="100%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <sub>Projects — health score per project, file-by-file validation status, hard vs soft failures</sub>
</div>

<br>

- **Projects** — health of every rules project the server has loaded. Click a row for the file-by-file fix-it list.

<div align="center">
  <img src="docs/screenshots/dev_p_users.png" alt="Users — active, inactive, never-called status" width="100%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <sub>Users & adoption — who is actively using the server, who has gone quiet, who never connected</sub>
</div>

<br>

- **Users** — who's connected, with `active` / `inactive` / `never-called` status.

<div align="center">
  <img src="docs/screenshots/dev_p_tools.png" alt="Tools — call counts, latency, most fetched docs" width="100%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <sub>Tools — call counts and latency per tool, plus which rule docs are fetched most</sub>
</div>

<br>

- **Tools** — call counts, latency, error rate per tool, and which docs are fetched most.

<div align="center">
  <img src="docs/screenshots/dev_p_activity.png" alt="Activity — live feed of all tool calls" width="100%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <sub>Activity — every tool call, the exact args, which editor sent it, and whether it succeeded</sub>
</div>

<br>

- **Searches** — recent queries + a **zero-result list** showing which topics have no docs yet.
- **Activity** — live feed of all tool calls.

<div align="center">
  <img src="docs/screenshots/dev_p_tokens.png" alt="API Tokens — generate and manage bearer tokens" width="100%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <sub>Tokens — generate per-user Bearer tokens for MCP authentication</sub>
</div>

<div align="center" style="margin-top:16px;">
  <img src="docs/screenshots/dev_p_token.png" alt="Manage Users — create accounts with user or admin roles" width="100%" style="border-radius:8px; border:2px solid #c8c8c8; box-shadow:0 8px 32px rgba(0,0,0,0.18);" />
  <sub>Manage Users — create team accounts, assign User or Admin roles</sub>
</div>

<br>

- **Setup** — editor connection instructions for Claude Code, Cursor, and Windsurf.

---

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `MCP_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` for LAN. |
| `MCP_PORT` | `3000` | HTTP port. |
| `MCP_CONFIG` | `mcp/config.toml` | Override config file path. |
| `MCP_DB_PATH` | `mcp/data/metrics.db` | SQLite file for usage metrics. |
| `MCP_INACTIVE_DAYS` | `2` | Days without a tool call before a user is "inactive". |
| `MCP_SNIPPET_SIZE` | `300` | Search snippet window in chars (clamped 50–5000). |
| `MCP_SERVER_LABEL` | `dev-agent-playbook` | Display name shown in the dashboard and MCP registration. |
| `KEYCLOAK_URL` | — | Required when `[enable].auth=true`. |
| `KEYCLOAK_REALM` | — | Same as above. |
| `MCP_CLIENT_ID` | — | Same as above. |
| `MCP_CLIENT_SECRET` | — | Same as above. |

## `mcp/config.toml`

```toml
[enable]
# When true, Bearer tokens are validated via Keycloak introspection.
# When false (default), users are identified by the X-MCP-User header or client IP.
auth = false
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Editor not showing server connected | URL wrong, server not reachable, or auth header missing | `curl <url>/healthz`; check firewall |
| Server exits with "No markdown rule docs loaded" | No project directories with `.md` files found | Check that your project folder is next to `mcp/`, not inside it |
| `validate-rules.py --check` reports `INDEX.md is out of date` | Frontmatter changed since INDEX was generated | `python scripts/validate-rules.py --regen-index` and commit the result |
| `validate-rules.py` reports `does not match the expected layout` | A `.md` file landed outside the recognized folders | Move it under one of `core/`, `architecture/`, `languages/<lang>/`, `patterns/`, `skills/`, `workflows/`, `gates/` — or delete it |
| Gate fails with "is not executable" | Script missing the executable bit | `chmod +x gates/scripts/<name>.sh` and commit |
| "Project not found" from a tool | Typo in project name | Ask the agent: *"what projects are available?"* |
| Agent gives outdated rules | Server cached files at startup | Restart the server after editing docs |
| Dashboard shows everyone as `anon@<ip>` | Users haven't set `X-MCP-User` | See the Setup page in the dashboard for the correct config snippet |

---

## Development

```bash
cd mcp
uv sync
uv run pytest                  # unit tests
uv run ruff check .            # lint
uv run ruff format --check .   # format check
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for conventions on adding patterns, skills, and rule docs.

## License

Apache License 2.0 — see [`LICENSE`](LICENSE).
