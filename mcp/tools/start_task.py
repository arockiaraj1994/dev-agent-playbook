"""tools/start_task.py — One-call orientation for AI agents.

`start_task(project, task)` is the canonical first call for any task. It
returns a single bundle containing:

  1. The project's always-on rules (core/guardrails.md + core/definition-of-done.md).
  2. The matched workflow doc (chosen by `triggers:` frontmatter, with BM25
     fallback when no trigger matches).
  3. A `## Next Calls` section listing the exact follow-up tool calls the
     agent should make next (skills + patterns referenced by the workflow).

The goal is to eliminate the "which tool first?" guess: one round-trip and
the agent has both the orientation and the call chain it needs.
"""

from __future__ import annotations

from mcp.types import TextContent, Tool

from loader import RuleDoc, RulesStore
from search import RulesSearchEngine

from .docs import _next_calls_section  # reuse the formatter

DEFINITIONS: list[Tool] = [
    Tool(
        name="start_task",
        description=(
            "Call this FIRST for any task. Pass a free-form sentence describing "
            "what the user asked for. Returns a bootstrap bundle: always-on "
            "guardrails + the matched workflow + `Next Calls` pointing at the "
            "skills and patterns to fetch next. Replaces the older "
            "list_projects → get_agents_md → get_pattern guessing chain."
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


def _bundle_text(
    project: str,
    task: str,
    guard: RuleDoc | None,
    dod: RuleDoc | None,
    workflow: RuleDoc | None,
) -> str:
    parts: list[str] = [f"# start_task — {project}\n\n_Task:_ {task}\n"]

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
            + _next_calls_section(workflow, project).lstrip()
        )
    else:
        parts.append(
            "## Matched workflow\n\n"
            "_No workflow matched. Try get_index or search_rules._"
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
    guard = store.get(project, "core/guardrails.md")
    dod = store.get(project, "core/definition-of-done.md")
    workflow = _match_workflow(store, engine, project, task)
    if workflow:
        setattr(ctx, "doc_path", f"{project}/{workflow.relative_path}")

    return [TextContent(type="text", text=_bundle_text(project, task, guard, dod, workflow))]
