# dev-agent-playbook

## Why this project?

Building apps from scratch is relatively easy with AI tools. The harder problem is **making changes in a large, active codebase** — adding features, fixing bugs, or refactoring across a team where everyone uses a different AI editor.

In an enterprise project, many developers contribute simultaneously, each with their own preferred AI tool: some use Cursor, some use Claude Code, some use Windsurf. The challenge is: how do you produce consistent, high-quality code regardless of which tool a developer is using?

Common solutions like `AGENTS.md` or `DESIGN.md` work, but they require you to dump **all** your project context into a single file upfront — context that isn't relevant to every task, every time. That overhead grows with the project.

**This project solves that with on-demand context delivery over MCP.** Instead of front-loading everything, your rule docs, architecture decisions, error conventions, patterns, and skills live on a central server. Every AI editor — regardless of vendor — connects to it and retrieves only the context relevant to the current task, via BM25 search and structured fetch tools. The server records every tool call so you can see exactly which rules are being used (and which gaps need filling).

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
uv run server.py
```

To bind on all interfaces (LAN / Docker):

```bash
MCP_HOST=0.0.0.0 MCP_PORT=3000 uv run server.py
```

**Requirements:** Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).

Once started, open the dashboard at **`http://localhost:3000/dashboard/`** — it shows connected editors, call activity, and which rules are being used. Editor connection instructions are in the dashboard under **Setup**.

---

## Adding a project

A project is a directory next to `mcp/` that holds rule docs for one codebase or domain. The server loads all projects at startup.

### Step 1 — Create the project directory

```
<your-project>/
  agents.md               ← required
  architecture.md         ← recommended
  error-conventions.md    ← recommended
  anti-patterns.md        ← recommended
  glossary.md             ← recommended
  patterns/
    <name>.md             ← one file per pattern
  skills/
    <action>.md           ← one file per workflow
```

Use `TEMPLATE.md` for copy-pasteable starters for each file type.

### Step 2 — Write `agents.md` first

This is the identity doc — the first thing the AI loads for your project. It should cover:

- What this codebase is and what the agent's role is
- Behavior rules (scope control, ask vs. guess, output discipline)
- Clean code principles specific to your stack
- Security defaults
- Testing requirements

Keep it focused. Agents load this on every session start, so every line should earn its place.

### Step 3 — Add reference docs

| File | What goes in it |
|------|----------------|
| `architecture.md` | Module map, service boundaries, tech stack, external integrations |
| `error-conventions.md` | How errors are structured, HTTP codes used, retry rules, what NOT to swallow |
| `anti-patterns.md` | Specific mistakes to avoid — with ❌ examples. Agents read this before writing code. |
| `glossary.md` | Domain terms so the agent uses your vocabulary, not generic terms |

### Step 4 — Add patterns

Patterns live in `patterns/<name>.md`. A pattern is a **canonical code example** — "this is what good code looks like for this scenario." Use them for recurring implementation shapes: SFTP routes, REST producers, auth flows, schema registration, etc.

Each pattern file should include:
- The rules that govern it (what's non-negotiable)
- The canonical code block
- Config/environment requirements
- Error scenarios and how they're handled

### Step 5 — Add skills

Skills live in `skills/<action>.md`. A skill is a **step-by-step workflow** — "do these steps in this order." Use them for multi-step tasks developers repeat: adding a connector, registering a schema, debugging a failing route, creating a migration.

Each skill file should include:
- A trigger line (when to use this skill)
- Numbered steps
- Constraints (what NOT to do as part of this workflow)

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

### Sample prompts

**Starting a task (agent loads context on its own)**
```
Add a new SFTP inbound route for payments to the apache-camel project.
I need to add a Kafka consumer for the orders topic — check the rules first.
Fix the retry logic on the payment route — follow our error conventions.
Refactor the invoice processor — load the anti-patterns before writing anything.
```

**Explicitly loading context**
```
Before we start, load the agents.md for the apache-camel project.
Get the architecture doc for this project so you understand the module layout.
Fetch the anti-patterns — I don't want those mistakes repeated.
Get the add-route skill and follow it step by step.
```

**Pulling a specific pattern**
```
Get the SFTP route pattern for apache-camel and use it as the base for the new route.
Use the REST producer pattern when implementing the billing API call.
Show me the error-conventions doc before we write the error handler.
```

**Searching when you're not sure which doc to fetch**
```
Search the rules for anything about dead letter queues.
Find docs about Keycloak authentication.
Search for how we handle schema registration.
Search for database migration conventions.
```

**Discovering what's available**
```
What projects are in the rules server?
List all the patterns for apache-camel.
What skills are available for this project?
```

---

## The dashboard

`http://<host>:3000/dashboard/` — open this to monitor usage and manage the server.

- **Dashboard** — live KPIs: connected editors, calls today, zero-result rate, hourly activity.
- **Users** — who's connected, with `active` / `inactive` / `never-called` status.
- **Tools** — call counts, latency, error rate per tool, and which docs are fetched most.
- **Searches** — recent queries + a **zero-result list** showing which topics have no docs yet.
- **Activity** — live feed of all tool calls.
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
