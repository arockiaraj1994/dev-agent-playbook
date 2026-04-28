# Templates

Copy-pasteable starting points for new rule docs. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for naming, the pattern-vs-skill rule, and the H1 convention.

The YAML frontmatter block is **optional** — delete it if you don't want it.

---

## `agents.md` — required for every project

```markdown
---
title: <Project> agents guide
description: Identity, behavior rules, and entry point for AI agents on <project>.
tags: [<stack-keywords>]
applies_to: [<project-name>]
---

# AGENTS.md — <Project> (<short stack>)

**Stack:** <one-line stack summary>

---

## IDENTITY

You are a senior engineer working on **<project>** — <one-paragraph description
of what the codebase does and what "good" looks like>.

You write minimal, correct, production-ready code.
You value working software over clever abstractions.
You fix root causes, not symptoms.

---

## CONTEXT DOCS

| Doc | Purpose |
|-----|---------|
| `./architecture.md` | Module map, tech stack, service boundaries |
| `./error-conventions.md` | Error handling standards |
| `./anti-patterns.md` | What NOT to generate — read before writing anything |
| `./glossary.md` | Domain terms |
| `./patterns/` | Canonical code patterns |
| `./skills/` | Step-by-step task workflows |

**Read `./anti-patterns.md` before writing any code.**

---

## SECTION 1 — AI BEHAVIOR CONSTRAINTS (HIGHEST PRIORITY)

### 1.1 Scope Control
- Change ONLY what is asked.
- Don't bundle unrelated improvements.

### 1.2 Context First
- Read existing code BEFORE writing anything new.
- Match existing naming, patterns, structure, formatting.

### 1.3 Ask, Don't Guess
- If requirements are ambiguous, ASK.
- If multiple valid approaches exist, list them and ask.

<!-- Add 1.4–1.6 as needed; see integration-manager/agents.md for a worked example. -->

---

## SECTION 2 — CLEAN CODE PRINCIPLES

<!-- Functions, files, naming, SOLID, DRY/YAGNI/KISS, comments. Tailor to the stack. -->

---

## SECTION 3 — DEPENDENCY & CHANGE HYGIENE

<!-- Adding deps, version pinning, git hygiene. -->

---

## SECTION 4 — TESTING

<!-- Required test coverage, test naming, what to mock. -->

---

## SECTION 5 — SECURITY DEFAULTS

- NEVER hardcode credentials, API keys, tokens.
- Validate all user input server-side.
- Don't log sensitive data.
<!-- Add stack-specific items. -->
```

---

## `patterns/<name>.md` — canonical code structure

```markdown
---
title: <Name> pattern for <project>
description: <one-sentence summary of what this pattern shows>.
tags: [<stack>, <feature>]
---

# Pattern: <Name> — <project context>

**Use this when:** <one-line trigger — the situation that calls for this pattern>.

**Avoids:** <link to anti-patterns this prevents>

---

## Structure

<!-- Folder layout, file roles, key types. Use a tree or table. -->

---

## Canonical example

```<lang>
<minimal, runnable example showing the pattern>
```

---

## Key rules

- <do/don't 1>
- <do/don't 2>

---

## See also

- `./glossary.md` — <terms used here>
- `./anti-patterns.md` — <related sections>
- `../skills/<action>.md` — <skill that uses this pattern>
```

---

## `skills/<action>.md` — step-by-step task workflow

```markdown
---
title: <Action> in <project>
description: <one-sentence summary of the task this skill walks through>.
tags: [<stack>, <task-type>]
---

# Skill: <Action> — <when to use>

**Trigger:** <user request that should invoke this skill, e.g. "add a new SFTP connector">.

**Prerequisites:**
- <repo cloned, deps installed, etc.>
- <patterns the user should be familiar with>

---

## Steps

1. **<Step name>** — <what to do, files to touch>.
   ```<lang>
   <code or command>
   ```

2. **<Step name>** — <what to do>.

3. **<Step name>** — <verification step>.

---

## Constraints

- <non-obvious constraint, e.g. "must run mvn clean before this">.
- <ordering rule, e.g. "Step 2 must complete before Step 3 in the same JVM">.

---

## Verification

- <how to confirm the change works>.
- <where to look in logs>.

---

## See also

- `../patterns/<name>.md` — <pattern this skill applies>.
```
