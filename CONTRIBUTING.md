# Contributing

This repo holds two things you can extend:

1. **Per-project rule docs** under `<project>/` (the bulk of contributions).
2. **The MCP server** under `mcp/` (Python).

This guide covers both. For copy-pasteable doc skeletons, see [`TEMPLATE.md`](TEMPLATE.md).

---

## Adding a new project ruleset

Create a directory next to `mcp/`. The minimum is one file:

```
my-project/
  agents.md         # required — identity + behavior for this codebase
```

Optional but recommended (the loader recognizes them by filename):

```
my-project/
  agents.md
  architecture.md           # module map, tech stack, service boundaries
  error-conventions.md      # HTTP codes, error formats, logging
  anti-patterns.md          # what NOT to do
  glossary.md               # domain terms
  patterns/
    <name>.md               # canonical code patterns
  skills/
    <action>.md             # step-by-step task workflows
```

After adding the directory, **restart any running MCP server** so it picks up the new project. Verify with:

```bash
python scripts/validate-rules.py
```

---

## Pattern vs Skill — the canonical rule

Authors frequently get this wrong. There is one rule:

> **Pattern** = canonical code structure. *"This is what good code in this stack looks like."* Reference material. Noun-named: `react.md`, `quarkus.md`, `keycloak-oidc.md`, `camel-sftp-route.md`.
>
> **Skill** = step-by-step task workflow. *"Do these steps in order."* Procedural. Verb-noun-named: `add-connector.md`, `register-schema.md`, `deploy-extension.md`.

If a doc tells you **what good code looks like**, it's a pattern. If it tells you **what to do, in order**, it's a skill. When in doubt: ask, don't split.

---

## File naming

- **Kebab-case** for filenames: `camel-sftp-route.md`, `register-schema.md`.
- **Patterns** are nouns (the thing): `quarkus.md`, `keycloak-oidc.md`.
- **Skills** are verb + noun (the action): `add-connector.md`, `deploy-extension.md`.
- One topic per file. If a pattern is 600 lines, split it; if it's two tightly related things, merge them.

## H1 convention

The first line of every doc is its title. The MCP server uses the H1 as the doc's display name when frontmatter is absent.

| Doc type | H1 format |
|----------|-----------|
| `agents.md` | `# AGENTS.md — <Project> (<short stack>)` |
| `architecture.md` | `# Architecture — <Project>` |
| `patterns/<name>.md` | `# Pattern: <Name> — <project context>` |
| `skills/<action>.md` | `# Skill: <Action> — <when to use>` |

---

## Optional YAML frontmatter

The MCP loader reads frontmatter when present and falls back to the H1 otherwise. Authors can adopt it incrementally.

```yaml
---
title: Quarkus pattern for Karavan
description: Canonical Quarkus structure — REST resources, services, CDI scopes.
tags: [quarkus, java, cdi, rest]
applies_to: [integration-manager]
---

# Pattern: Quarkus — Apache Camel Karavan
...
```

Recognized fields:

| Field | Type | Used for |
|-------|------|----------|
| `title` | string | Display name; weighted 2× in BM25 search. |
| `description` | string | Short summary returned by `list_rule_docs`. |
| `tags` | list of strings | Weighted 2× in BM25 search. |
| `applies_to` | list of strings | Project scopes; informational for now. |

Unknown keys are ignored. No frontmatter at all is fine.

---

## Cross-referencing

- Link to **`./glossary.md`** the first time a domain term appears in a doc.
- When a pattern explicitly avoids an anti-pattern, link to it: `(see ./anti-patterns.md §SECURITY)`.
- Patterns and skills can reference each other: skills usually point at the patterns they implement.

---

## PR conventions

- **Title:** `rules(<project>): short imperative description` for rule changes; `mcp: …` for server changes.
- **Scope:** one project per PR when possible. Don't bundle a server refactor with a rule rewrite.
- **CI must pass:** ruff lint, the rule validator (`scripts/validate-rules.py`), and unit tests.

---

## Working on the MCP server

```bash
cd mcp
uv sync                       # install deps + dev deps
uv run pytest                 # run tests
uv run ruff check .           # lint
uv run ruff format --check .  # check formatting (no edits)
```

The server reads rules from the parent directory of `mcp/` at startup. To test against a smaller corpus, point `MCP_CONFIG` at a `config.toml` whose layout you control, or create a minimal sandbox repo.

When you change a tool's name or schema, bump the server version in `mcp/pyproject.toml` and add an entry to [`CHANGELOG.md`](CHANGELOG.md).

---

## Style

- Prefer **imperative voice** in rule docs ("Use Bean Validation", not "You should use Bean Validation").
- No marketing language. AI agents and humans both prefer dense, scannable prose.
- Short sections with explicit headings beat long flowing prose — the BM25 index weights headings higher.
- Code blocks should be runnable or near-runnable; avoid pseudocode unless it's clearly labeled.
