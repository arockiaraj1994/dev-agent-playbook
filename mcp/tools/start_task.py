"""tools/start_task.py — One-call orientation for AI agents.

`start_task(project, task)` is the canonical first call for any task. It
returns a single bundle containing:

  1. The project's IDENTITY section, lifted from AGENTS.md.
  2. The project's always-on rules (core/guardrails.md + core/definition-of-done.md).
  3. The matched workflow doc (chosen by `triggers:` frontmatter, with BM25
     fallback when no trigger matches).
  4. A `## Next Calls` section listing the exact follow-up tool calls the
     agent should make next (skills + patterns referenced by the workflow).

The goal is to eliminate the "which tool first?" guess: one round-trip and
the agent has both the orientation and the call chain it needs. Inlining
IDENTITY is what removes the reason to reach for get_agents_md, which is a
6KB doc that mostly restates the guardrails already bundled here.
"""

from __future__ import annotations

import re

from mcp.types import TextContent, Tool

from loader import RuleDoc, RulesStore
from search import RulesSearchEngine

from .docs import _next_calls_section  # reuse the formatter

DEFINITIONS: list[Tool] = [
    Tool(
        name="start_task",
        description=(
            "ALWAYS call this FIRST for any coding task in a project — before "
            "get_agents_md or any other get_* tool. Pass a free-form sentence "
            "describing what the user asked for. Returns a bootstrap bundle: "
            "the project's identity + always-on guardrails + the matched "
            "workflow + `Next Calls` pointing at the skills and patterns to "
            "fetch next."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name. Use list_projects to discover values.",
                },
                "task": {
                    "type": "string",
                    "description": (
                        "Free-form task description (e.g. 'fix a bug in the SFTP route' "
                        "or 'add a new connector for Quarkus')."
                    ),
                },
            },
            "required": ["project", "task"],
        },
    ),
]

_NAMES = {"start_task"}


# ---------------------------------------------------------------------------
# Workflow matching
# ---------------------------------------------------------------------------


def _match_workflow(
    store: RulesStore, engine: RulesSearchEngine, project: str, task: str
) -> RuleDoc | None:
    """Pick the most relevant workflow doc for `task`.

    1. Exact-ish match against frontmatter `triggers:` (case-insensitive
       substring match in either direction).
    2. Fallback to BM25 search restricted to doc_type=workflow.
    """
    task_lc = task.lower()
    workflows = store.of_type(project, "workflow")

    # Trigger-phrase pass.
    for wf in workflows:
        triggers = wf.metadata.get("triggers") or []
        if not isinstance(triggers, list):
            continue
        for trig in triggers:
            if not isinstance(trig, str) or not trig.strip():
                continue
            t = trig.strip().lower()
            if t in task_lc or task_lc in t:
                return wf

    # BM25 fallback.
    if not workflows:
        return None
    results = engine.search(query=task, project=project, doc_type="workflow", top_k=1)
    if not results:
        return None
    top = results[0]
    return store.get(project, top.relative_path)


# The IDENTITY block runs to the next H2, or to EOF if it is the last section.
_IDENTITY_RE = re.compile(
    r"^##\s+IDENTITY\b.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
)


def _identity_section(agents: RuleDoc | None, max_chars: int = 1200) -> str:
    """The `## IDENTITY` block of AGENTS.md, or "" if absent.

    Deliberately narrow: the rest of AGENTS.md restates the guardrails that
    this bundle already inlines, so we never fall back to the whole doc.
    """
    if not agents:
        return ""
    match = _IDENTITY_RE.search(agents.content)
    if not match:
        return ""
    # Sections are separated by `---` rules; drop the trailing one.
    body = match.group(0).strip().rstrip("-").strip()
    if not body:
        return ""
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "\n\n_(truncated — call get_agents_md for the rest)_"
    return body


def _bundle_text(
    project: str,
    task: str,
    identity: str,
    guard: RuleDoc | None,
    dod: RuleDoc | None,
    workflow: RuleDoc | None,
) -> str:
    parts: list[str] = [f"# start_task — {project}\n\n_Task:_ {task}\n"]

    if identity:
        parts.append(identity)

    if guard or dod:
        parts.append("## Always-on rules\n")
        if guard:
            parts.append("### Guardrails\n\n" + guard.content.strip())
        if dod:
            parts.append("### Definition of Done\n\n" + dod.content.strip())
    else:
        parts.append(
            "_No core/guardrails.md or core/definition-of-done.md found — "
            "ask the project maintainer to add them._"
        )

    if workflow:
        parts.append(
            f"## Matched workflow: `{workflow.name}`\n\n"
            f"_Path:_ `{workflow.relative_path}`\n\n"
            + workflow.content.strip()
            # Keep the leading blank lines: without them the `---` rule collides
            # with the last line of the workflow body and stops being a rule.
            + _next_calls_section(workflow, project)
        )
    else:
        parts.append(
            "## Matched workflow\n\n"
            "_No workflow matched. Try `find_rules(project=\"" + project + "\")` "
            "to list the available docs._"
        )

    return "\n\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def dispatch(
    name: str,
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent] | None:
    if name not in _NAMES:
        return None

    project = (arguments.get("project") or "").strip()
    task = (arguments.get("task") or "").strip()

    if not project or not task:
        setattr(ctx, "status", "error")
        return [
            TextContent(
                type="text",
                text="Both `project` and `task` are required.",
            )
        ]

    if project not in store.projects():
        setattr(ctx, "status", "not_found")
        return [
            TextContent(
                type="text",
                text=(
                    f"Project '{project}' not found. "
                    "Call list_projects to see valid names."
                ),
            )
        ]

    setattr(ctx, "query", task)
    identity = _identity_section(store.get(project, "AGENTS.md"))
    guard = store.get(project, "core/guardrails.md")
    dod = store.get(project, "core/definition-of-done.md")
    workflow = _match_workflow(store, engine, project, task)
    if workflow:
        setattr(ctx, "doc_path", f"{project}/{workflow.relative_path}")

    text = _bundle_text(project, task, identity, guard, dod, workflow)
    return [TextContent(type="text", text=text)]
