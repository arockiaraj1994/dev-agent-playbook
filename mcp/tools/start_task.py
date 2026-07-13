"""tools/start_task.py - One-call orientation for AI agents.

`start_task(task, project?, requirement?)` is the canonical first call for any
task. `project` is optional when exactly one standards project exists.
It returns a single bundle containing:

  1. The project's IDENTITY section, lifted from AGENTS.md.
  2. The project's always-on rules (core/guardrails.md + core/definition-of-done.md).
  3. When `requirement=` is set: the story (FULL) + parent PRD (SUMMARY), or
     the PRD (FULL) + one-line story list - server-side tree walk, no chaining.
  4. The matched workflow doc (chosen by `triggers:` frontmatter, with BM25
     fallback when no trigger matches).
  5. A `## Next Calls` section from the workflow's `see_also:` and, when a
     story is linked, from the story's `targets:` - all as `get_doc(kind=…)`.
"""

from __future__ import annotations

import re

from mcp.types import TextContent, Tool

from loader import RuleDoc, RulesStore
from search import RulesSearchEngine

from .docs import _next_calls_lines, _render_next_calls, _resolve_project
from .requirements import _meta_str, _prd_summary, _title

DEFINITIONS: list[Tool] = [
    Tool(
        name="start_task",
        description=(
            "ALWAYS call this FIRST for any coding task - before get_doc or any "
            "other tool. Pass a free-form sentence describing what the user "
            "asked for. CRITICAL: `project` MUST be the basename of the user's "
            "current workspace directory (never invent another project). "
            "Optional only when exactly one standards project exists. "
            "Optionally pass requirement=ST-114 or requirement=PRD-003 to pull "
            "the linked requirement into the bundle. Returns: identity + "
            "always-on guardrails + (optional) requirement + matched workflow "
            "+ Next Calls."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": (
                        "Basename of the user's current workspace directory "
                        "(e.g. cwd .../NexRe → \"nexre\" or \"NexRe\"). "
                        "Case-insensitive. NEVER substitute a different "
                        "project. Inferred only when exactly one standards "
                        "project exists."
                    ),
                },
                "task": {
                    "type": "string",
                    "description": (
                        "Free-form task description (e.g. 'fix a bug in the SFTP route' "
                        "or 'add a new connector for Quarkus')."
                    ),
                },
                "requirement": {
                    "type": "string",
                    "description": (
                        "Optional requirement id: ST-114 or PRD-003. "
                        "Server resolves the tree (story→PRD or PRD→stories) "
                        "in one call."
                    ),
                },
            },
            "required": ["task"],
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
    workflows = store.of_type(project, "workflow", corpus="standards")

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
    results = engine.search(
        query=task, project=project, doc_type="workflow", top_k=1, corpus="standards"
    )
    if not results:
        return None
    top = results[0]
    return store.get(project, top.relative_path, corpus="standards")


# The IDENTITY block runs to the next H2, or to EOF if it is the last section.
_IDENTITY_RE = re.compile(
    r"^##\s+IDENTITY\b.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL | re.IGNORECASE
)


def _identity_section(agents: RuleDoc | None, max_chars: int = 1200) -> str:
    """The `## IDENTITY` block of AGENTS.md, or "" if absent."""
    if not agents:
        return ""
    match = _IDENTITY_RE.search(agents.content)
    if not match:
        return ""
    body = match.group(0).strip().rstrip("-").strip()
    if not body:
        return ""
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "\n\n_(truncated - call get_agents_md for the rest)_"
    return body


def _depends_warnings(store: RulesStore, story: RuleDoc) -> list[str]:
    raw = story.metadata.get("depends_on") or []
    if not isinstance(raw, list):
        return []
    warnings: list[str] = []
    for dep in raw:
        if not isinstance(dep, str) or not dep.strip():
            continue
        dep_id = dep.strip()
        other = store.find_by_id("requirements", story.project, dep_id)
        if other is None:
            warnings.append(f"⚠ {story.name} depends on {dep_id} (not found).")
            continue
        status = _meta_str(other, "status", "draft")
        if status != "shipped":
            warnings.append(f"⚠ {story.name} depends on {dep_id} (status: {status}).")
    return warnings


def _requirement_bundle(
    store: RulesStore, project: str, req_id: str
) -> tuple[str, str | None, list[str]]:
    """Build the requirement section.

    Returns (markdown, status_or_error, target_call_lines). The markdown never
    contains its own `## Next Calls` - the target bullets are returned
    separately so the caller can merge them into one section at the end of the
    bundle. status_or_error is None on success, 'not_found' when missing, or
    'error' on an unexpected type.
    """
    doc = store.find_by_id("requirements", project, req_id)
    if not doc:
        return (
            f"Requirement '{req_id}' not found in {project}. Call list_requirements.",
            "not_found",
            [],
        )

    banner = ""
    status = _meta_str(doc, "status", "draft")
    if status == "shipped":
        banner = (
            f"> ⚠ **Warning:** `{doc.name}` has status `shipped` - "
            "treat as frozen historical context, not an active handoff.\n\n"
        )

    if doc.doc_type == "story":
        warnings = _depends_warnings(store, doc)
        warn_block = ("\n".join(warnings) + "\n\n") if warnings else ""
        prd = store.prd_of(doc)
        parts = [
            banner + warn_block + f"## Requirement: `{doc.name}` (story)\n\n"
            f"_Title:_ {_title(doc)}  \n"
            f"_Status:_ {status}  \n"
            f"_Priority:_ {_meta_str(doc, 'priority', ' - ')}  \n"
            f"_Path:_ `{doc.project}/{doc.relative_path}`\n\n"
            + doc.content.strip()
        ]
        if prd:
            parts.append("## Parent PRD (summary)\n\n" + _prd_summary(prd))
        target_lines = _next_calls_lines(doc, project, key="targets")
        return "\n\n".join(parts), None, target_lines

    if doc.doc_type == "prd":
        stories = store.stories_of(doc)
        story_lines = (
            "\n".join(
                f"- **{s.name}** ({_meta_str(s, 'status', 'draft')}) - {_title(s)}" for s in stories
            )
            if stories
            else "_No stories yet._"
        )
        return (
            banner + f"## Requirement: `{doc.name}` (PRD)\n\n"
            f"_Title:_ {_title(doc)}  \n"
            f"_Status:_ {status}  \n"
            f"_Path:_ `{doc.project}/{doc.relative_path}`\n\n"
            + doc.content.strip()
            + "\n\n## Stories\n\n"
            + story_lines,
            None,
            [],
        )

    return f"Requirement '{req_id}' has unexpected type '{doc.doc_type}'.", "error", []


def _bundle_text(
    project: str,
    task: str,
    identity: str,
    guard: RuleDoc | None,
    dod: RuleDoc | None,
    workflow: RuleDoc | None,
    requirement_md: str | None = None,
    target_lines: list[str] | None = None,
) -> str:
    parts: list[str] = [f"# start_task - {project}\n\n_Task:_ {task}\n"]

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
            "_No core/guardrails.md or core/definition-of-done.md found - "
            "ask the project maintainer to add them._"
        )

    if requirement_md:
        parts.append(requirement_md)

    if workflow:
        parts.append(
            f"## Matched workflow: `{workflow.name}`\n\n"
            f"_Path:_ `{workflow.relative_path}`\n\n" + workflow.content.strip()
        )
    else:
        parts.append(
            "## Matched workflow\n\n"
            '_No workflow matched. Try `find_rules(project="' + project + '")` '
            "to list the available docs._"
        )

    # One consolidated Next Calls at the very end: story `targets:` first (the
    # WHAT→HOW bridge), then the workflow's `see_also:`, de-duplicated.
    next_lines: list[str] = list(target_lines or [])
    if workflow:
        for line in _next_calls_lines(workflow, project):
            if line not in next_lines:
                next_lines.append(line)
    parts.append(_render_next_calls(next_lines).lstrip("\n"))

    return "\n\n".join(p for p in parts if p) + "\n"


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

    task = (arguments.get("task") or "").strip()
    requirement = (arguments.get("requirement") or "").strip() or None

    if not task:
        ctx.status = "error"
        return [
            TextContent(
                type="text",
                text="`task` is required.",
            )
        ]

    resolution = _resolve_project(store, arguments.get("project"), corpus="standards")
    if not resolution.ok:
        ctx.status = resolution.status
        return [
            TextContent(
                type="text",
                text=resolution.error_text or "Project resolution failed.",
            )
        ]
    project = resolution.project
    assert project is not None

    ctx.query = task
    if requirement:
        ctx.requirement_id = requirement

    identity = _identity_section(store.get(project, "AGENTS.md", corpus="standards"))
    guard = store.get(project, "core/guardrails.md", corpus="standards")
    dod = store.get(project, "core/definition-of-done.md", corpus="standards")
    workflow = _match_workflow(store, engine, project, task)
    if workflow:
        ctx.doc_path = f"{project}/{workflow.relative_path}"

    requirement_md: str | None = None
    target_lines: list[str] = []
    if requirement:
        requirement_md, err, target_lines = _requirement_bundle(store, project, requirement)
        if err == "not_found":
            ctx.status = "not_found"
            return [TextContent(type="text", text=requirement_md)]
        if err == "error":
            ctx.status = "error"
            return [TextContent(type="text", text=requirement_md)]

    text = _bundle_text(
        project, task, identity, guard, dod, workflow, requirement_md, target_lines
    )
    return [TextContent(type="text", text=text)]
