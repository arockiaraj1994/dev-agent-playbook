"""tools/docs.py - Unified get_doc MCP tool.

One tool replaces the former get_agents_md / get_guardrails / get_architecture /
get_language_rules / get_pattern / get_skill / get_workflow / get_gate /
get_requirement surface:

  get_doc(kind=..., project?, name?, doc?, depth?)

Corpus is implied by kind (`requirement` → requirements; everything else →
standards). Each return body is the doc content plus, if the doc declares
`see_also` / `targets` in frontmatter, a `## Next Calls` section that names
the exact `get_doc(...)` calls the agent should make next.
"""

from __future__ import annotations

import logging

from mcp.types import TextContent, Tool

from loader import SEE_ALSO_CORE, SEE_ALSO_TOOLS, RuleDoc, RulesStore, resolve_rules_root
from search import RulesSearchEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_LANGUAGE_DOCS = ["standards", "testing", "anti-patterns"]
_WORKFLOW_NAMES = ["new-feature", "bug-fix", "security-fix", "refactor"]
_KINDS = [
    "agents",
    "guardrails",
    "architecture",
    "language",
    "pattern",
    "skill",
    "workflow",
    "gate",
    "requirement",
]
_KINDS_REQUIRING_NAME = frozenset({"language", "pattern", "skill", "workflow", "requirement"})
_DEPTHS = ["self", "with_parent", "with_children"]

DEFINITIONS: list[Tool] = [
    Tool(
        name="get_doc",
        description=(
            "Fetch one standards or requirement doc by kind. Not the entry "
            "point - use start_task first for coding tasks. `name` identifies "
            "the doc within its kind; `project` is optional when a single "
            "project exists. Corpus is implied by kind."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "description": (
                        "Doc family: agents | guardrails | architecture | "
                        "language | pattern | skill | workflow | gate | requirement."
                    ),
                    "enum": _KINDS,
                },
                "project": {
                    "type": "string",
                    "description": (
                        "Basename of the user's current workspace directory "
                        "(case-insensitive match to standards/). NEVER invent "
                        "another project. Inferred when one standards project "
                        "exists. kind=requirement: may omit to search all "
                        "requirements projects by id."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Doc identifier (meaning set by kind): pattern/skill/"
                        "workflow name, language code, ADR slug, gate script, "
                        "or requirement id (ST-101 / PRD-003). Required for "
                        "language, pattern, skill, workflow, requirement."
                    ),
                },
                "doc": {
                    "type": "string",
                    "description": (
                        "kind=language only: standards | testing | anti-patterns "
                        "(default: standards)."
                    ),
                    "enum": _LANGUAGE_DOCS,
                    "default": "standards",
                },
                "depth": {
                    "type": "string",
                    "description": (
                        "kind=requirement only: self (default) | with_parent "
                        "(story to PRD) | with_children (PRD to stories)."
                    ),
                    "enum": _DEPTHS,
                    "default": "self",
                },
            },
            "required": ["kind"],
        },
    ),
]


_NAMES = {t.name for t in DEFINITIONS}


# ---------------------------------------------------------------------------
# Project resolution (shared with start_task)
# ---------------------------------------------------------------------------


class ProjectResolution:
    """Result of resolving an optional project argument."""

    __slots__ = ("project", "error_text", "status")

    def __init__(
        self,
        project: str | None = None,
        *,
        error_text: str | None = None,
        status: str = "ok",
    ) -> None:
        self.project = project
        self.error_text = error_text
        self.status = status

    @property
    def ok(self) -> bool:
        """True when resolution produced no error (project may still be None
        for cross-project id lookup)."""
        return self.error_text is None


def _canonical_project(given: str, known: list[str]) -> str | None:
    """Return the corpus project name matching `given` (exact, then case-insensitive)."""
    if given in known:
        return given
    by_lower = {p.lower(): p for p in known}
    return by_lower.get(given.lower())


def _resolve_project(
    store: RulesStore,
    project_arg: str | None,
    *,
    corpus: str = "standards",
    allow_omit_for_cross_lookup: bool = False,
) -> ProjectResolution:
    """Infer / validate project.

 - given + valid (exact or case-insensitive cwd basename) → use canonical name
 - given + invalid → not_found with list
 - omitted + exactly one project in corpus → infer
 - omitted + many → needs_project; tell caller to pass workspace directory basename
 - omitted + allow_omit_for_cross_lookup → ok with project=None (caller looks up by id)
    """
    given = (project_arg or "").strip()
    known = list(store.projects(corpus=corpus))
    if not known and corpus == "standards":
        known = list(store.projects())
    all_known = list(store.projects(corpus=None)) or known

    if given:
        canonical = _canonical_project(given, known) or _canonical_project(
            given, all_known
        )
        if canonical is not None:
            return ProjectResolution(canonical)
        listing = "\n".join(f"- {p}" for p in known) or "(none)"
        return ProjectResolution(
            error_text=(
                f"Project '{given}' not found. "
                "`project` must be the basename of your current workspace "
                "directory (matched to a standards/ folder). Available:\n"
                f"{listing}\n"
                "Call list_projects to refresh."
            ),
            status="not_found",
        )

    if allow_omit_for_cross_lookup:
        return ProjectResolution(None)

    if len(known) == 1:
        return ProjectResolution(known[0])

    if not known:
        return ProjectResolution(
            error_text="No projects found. Call list_projects.",
            status="not_found",
        )

    listing = "\n".join(f"- {p}" for p in known)
    return ProjectResolution(
        error_text=(
            "Which project? Pass `project=` as the basename of your current "
            "workspace directory (e.g. folder NexRe → project=\"nexre\"). "
            "Available:\n"
            f"{listing}\n"
            "Or call list_projects."
        ),
        status="needs_project",
    )


# ---------------------------------------------------------------------------
# Shared helpers - Next Calls
# ---------------------------------------------------------------------------


def _next_calls_lines(doc: RuleDoc, project: str, key: str = "see_also") -> list[str]:
    """Return the rendered `- ...` call bullets from a frontmatter list field.

    Default key is `see_also` (standards docs). Stories use `targets:` - same
    `<kind>:<name>` vocabulary, same renderer. Returns the bullet lines only
    (no header), so callers can merge several sources into one section.
    """
    raw = doc.metadata.get(key) or []
    if not isinstance(raw, list) or not raw:
        return []

    lines: list[str] = []
    for entry in raw:
        if not isinstance(entry, str) or ":" not in entry:
            continue
        kind, _, name = entry.partition(":")
        kind = kind.strip()
        name = name.strip()
        if not kind or not name:
            continue
        call = _format_call(kind, project, name)
        if call:
            lines.append(f"- {call}")
    return lines


def _render_next_calls(lines: list[str]) -> str:
    """Wrap already-rendered call bullets in a `## Next Calls` section."""
    if not lines:
        return ""
    return "\n\n---\n\n## Next Calls\n\n" + "\n".join(lines) + "\n"


def _next_calls_section(doc: RuleDoc, project: str, key: str = "see_also") -> str:
    """Render a `## Next Calls` block from a single frontmatter list field."""
    return _render_next_calls(_next_calls_lines(doc, project, key))


def _format_call(kind: str, project: str, name: str) -> str | None:
    """Render a see_also/targets entry as a get_doc (or other entry-point) call."""
    if kind == "tool":
        return _format_tool_call(project, name)
    if kind == "core":
        if name in SEE_ALSO_CORE:
            return (
                f'`get_doc(project="{project}", kind="guardrails")` - always-on rules'
            )
        return None
    if kind == "pattern":
        return (
            f'`get_doc(project="{project}", kind="pattern", name="{name}")` '
            f" - pattern `{name}`"
        )
    if kind == "skill":
        return (
            f'`get_doc(project="{project}", kind="skill", name="{name}")` - skill `{name}`'
        )
    if kind == "workflow":
        return (
            f'`get_doc(project="{project}", kind="workflow", name="{name}")` '
            f" - workflow `{name}`"
        )
    if kind in ("gate", "gates"):
        if name in ("", "gate", "README"):
            return f'`get_doc(project="{project}", kind="gate")` - gate `{name or "README"}`'
        return (
            f'`get_doc(project="{project}", kind="gate", name="{name}")` - gate `{name}`'
        )
    if kind == "language":
        if "/" in name:
            lang, doc = name.split("/", 1)
            return (
                f'`get_doc(project="{project}", kind="language", name="{lang}", '
                f'doc="{doc}")` - {lang} {doc}'
            )
        return (
            f'`get_doc(project="{project}", kind="language", name="{name}")` '
            f" - {name} standards"
        )
    if kind == "architecture":
        if name in ("", "overview"):
            return f'`get_doc(project="{project}", kind="architecture")` - overview'
        return (
            f'`get_doc(project="{project}", kind="architecture", name="{name}")` '
            f" - ADR `{name}`"
        )
    if kind == "requirement":
        return (
            f'`get_doc(project="{project}", kind="requirement", name="{name}")` '
            f" - requirement `{name}`"
        )
    if kind == "agents":
        return f'`get_doc(project="{project}", kind="agents")` - AGENTS.md'
    return None


def _format_tool_call(project: str, name: str) -> str | None:
    """Render a `see_also: [tool:<name>]` entry as a literal tool call."""
    if name not in SEE_ALSO_TOOLS:
        return None
    if name == "start_task":
        return (
            f'**START HERE** - `start_task(project="{project}", '
            'task="<one sentence describing what the user asked for>")` '
            " - guardrails + matched workflow in one call"
        )
    if name in ("get_guardrails", "get_doc"):
        return f'`get_doc(project="{project}", kind="guardrails")` - always-on rules'
    if name == "find_rules":
        return f'`find_rules(project="{project}")` - list every rule doc (add `query=` to search)'
    if name == "list_requirements":
        return f'`list_requirements(project="{project}")` - catalogue PRDs/stories'
    if name == "get_requirement":
        # Legacy frontmatter alias - still render as get_doc.
        return (
            f'`get_doc(project="{project}", kind="requirement", name="<id>")` '
            " - fetch a PRD or story"
        )
    if name == "start_requirement":
        return (
            f'`start_requirement(project="{project}", intent="<what to specify>")` '
            " - PM authoring bootstrap"
        )
    return "`list_projects()` - available projects"


def _render(doc: RuleDoc, project: str) -> str:
    return doc.content + _next_calls_section(doc, project)


def _not_found(message: str) -> list[TextContent]:
    return [TextContent(type="text", text=message)]


def _set_path(ctx: object, path: str | None) -> None:
    ctx.doc_path = path


def _set_status(ctx: object, status: str) -> None:
    ctx.status = status


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

    kind = (arguments.get("kind") or "").strip()
    if kind not in _KINDS:
        _set_status(ctx, "error")
        return _not_found(f"`kind` must be one of {_KINDS}; got '{kind or '(empty)'}'.")

    doc_name = (arguments.get("name") or "").strip()
    if kind in _KINDS_REQUIRING_NAME and not doc_name:
        _set_status(ctx, "error")
        return _not_found(f"`name` is required when kind='{kind}'.")

    # requirement: allow omitting project for cross-project id lookup
    if kind == "requirement":
        return _get_requirement(store, ctx, arguments)

    resolution = _resolve_project(store, arguments.get("project"), corpus="standards")
    if not resolution.ok:
        _set_status(ctx, resolution.status)
        return _not_found(resolution.error_text or "Project resolution failed.")
    project = resolution.project
    assert project is not None

    if kind == "agents":
        return _fetch(store, ctx, project, "AGENTS.md", "AGENTS.md")

    if kind == "guardrails":
        return _get_guardrails(store, ctx, project)

    if kind == "architecture":
        adr = doc_name
        if adr:
            rel = f"architecture/decisions/{adr}.md"
            return _fetch(store, ctx, project, rel, f"ADR '{adr}'")
        return _fetch(store, ctx, project, "architecture/overview.md", "architecture/overview.md")

    if kind == "language":
        language = doc_name
        doc = (arguments.get("doc") or "standards").strip()
        if doc not in _LANGUAGE_DOCS:
            _set_status(ctx, "error")
            return _not_found(f"`doc` must be one of {_LANGUAGE_DOCS}; got '{doc}'.")
        rel = f"languages/{language}/{doc}.md"
        return _fetch(store, ctx, project, rel, f"{language}/{doc}")

    if kind == "pattern":
        return _fetch(store, ctx, project, f"patterns/{doc_name}.md", f"pattern '{doc_name}'")

    if kind == "skill":
        return _fetch(store, ctx, project, f"skills/{doc_name}.md", f"skill '{doc_name}'")

    if kind == "workflow":
        return _fetch(store, ctx, project, f"workflows/{doc_name}.md", f"workflow '{doc_name}'")

    if kind == "gate":
        return _get_gate(store, ctx, project, doc_name)

    return None


# ---------------------------------------------------------------------------
# Per-kind implementations
# ---------------------------------------------------------------------------


def _fetch(
    store: RulesStore,
    ctx: object,
    project: str,
    relative_path: str,
    label: str,
) -> list[TextContent]:
    _set_path(ctx, f"{project}/{relative_path}")
    doc = store.get(project, relative_path, corpus="standards")
    if not doc:
        # Fall back for unit tests / single-corpus stores
        doc = store.get(project, relative_path)
    if not doc:
        _set_status(ctx, "not_found")
        return _not_found(
            f"{label} not found for project '{project}' "
            f"(expected at {relative_path}). "
            "Call find_rules to see what is available."
        )
    return [TextContent(type="text", text=_render(doc, project))]


def _get_guardrails(store: RulesStore, ctx: object, project: str) -> list[TextContent]:
    _set_path(ctx, f"{project}/core/guardrails.md+definition-of-done.md")
    guard = store.get(project, "core/guardrails.md", corpus="standards") or store.get(
        project, "core/guardrails.md"
    )
    dod = store.get(project, "core/definition-of-done.md", corpus="standards") or store.get(
        project, "core/definition-of-done.md"
    )
    if not guard and not dod:
        _set_status(ctx, "not_found")
        return _not_found(
            f"No core/guardrails.md or core/definition-of-done.md for project '{project}'."
        )
    parts: list[str] = []
    if guard:
        parts.append("# Guardrails (always-on)\n\n" + guard.content.strip())
    if dod:
        parts.append("# Definition of Done\n\n" + dod.content.strip())
    return [TextContent(type="text", text="\n\n---\n\n".join(parts))]


def _get_gate(store: RulesStore, ctx: object, project: str, name: str) -> list[TextContent]:
    gate = store.get(project, "gates/README.md", corpus="standards") or store.get(
        project, "gates/README.md"
    )
    if not gate:
        _set_status(ctx, "not_found")
        _set_path(ctx, f"{project}/gates/README.md")
        return _not_found(f"No gates/README.md for project '{project}'.")
    scripts = gate.metadata.get("gate_scripts") or []

    if not name:
        _set_path(ctx, f"{project}/gates/README.md")
        listing = (
            "\n\n## Available scripts\n\n" + "\n".join(f"- `gates/scripts/{s}`" for s in scripts)
            if scripts
            else "\n\n_No executable scripts under gates/scripts/._\n"
        )
        return [TextContent(type="text", text=gate.content + listing)]

    # Specific script requested - locate it among gate_scripts.
    script_filename = name if name.endswith(".sh") else f"{name}.sh"
    _set_path(ctx, f"{project}/gates/scripts/{script_filename}")
    if script_filename not in scripts:
        _set_status(ctx, "not_found")
        return _not_found(
            f"Gate script '{script_filename}' not found for project '{project}'. "
            f"Available: {scripts or '[]'}."
        )
    text = (
        f"# Gate: {script_filename}\n\n"
        f"Path: `{project}/gates/scripts/{script_filename}`\n\n"
        "The MCP server does not execute gate scripts. To run it locally:\n\n"
        f"```\nbash {project}/gates/scripts/{script_filename}\n```\n"
        + _script_preview(project, script_filename)
        + "\nSee the gate README for what this script enforces:\n\n"
        + gate.content
    )
    return [TextContent(type="text", text=text)]


def _script_preview(project: str, script_filename: str, max_lines: int = 40) -> str:
    """First lines of a gate script, for the agent to read (never executed).

    `script_filename` is already validated against the `gate_scripts` directory
    listing by the caller, so it cannot escape gates/scripts/.
    """
    path = resolve_rules_root() / project / "gates" / "scripts" / script_filename
    try:
        with path.open(encoding="utf-8") as fh:
            lines = [next(fh, None) for _ in range(max_lines)]
    except OSError as exc:
        logger.warning("Could not read gate script %s: %s", path, exc)
        return ""
    body = "".join(line for line in lines if line is not None).rstrip()
    if not body:
        return ""
    truncated = "\n… (truncated)" if lines[-1] is not None else ""
    return f"\n## First {max_lines} lines\n\n```bash\n{body}{truncated}\n```\n"


def _get_requirement(store: RulesStore, ctx: object, arguments: dict) -> list[TextContent]:
    """kind=requirement - former get_requirement tool."""
    # Local import avoids a circular dependency at module load time
    # (requirements.py imports Next Calls helpers from this module).
    from .requirements import _find_req, _meta_str, _prd_summary, _title

    req_id = (arguments.get("name") or "").strip()
    project_arg = (arguments.get("project") or "").strip() or None
    depth = (arguments.get("depth") or "self").strip()
    if depth not in _DEPTHS:
        _set_status(ctx, "error")
        return _not_found(f"`depth` must be one of {_DEPTHS}; got '{depth}'.")

    if project_arg:
        resolution = _resolve_project(store, project_arg, corpus="requirements")
        # Also accept standards project names (same slug).
        if not resolution.ok:
            resolution = _resolve_project(store, project_arg, corpus="standards")
        if not resolution.ok:
            _set_status(ctx, resolution.status)
            return _not_found(resolution.error_text or "Project not found.")
        project_arg = resolution.project

    doc = _find_req(store, req_id, project_arg)
    if not doc:
        _set_status(ctx, "not_found")
        return _not_found(f"Requirement '{req_id}' not found. Call list_requirements.")

    ctx.doc_path = f"{doc.corpus}/{doc.project}/{doc.relative_path}"
    ctx.requirement_id = doc.name
    ctx.corpus = "requirements"

    parts: list[str] = [
        f"# {doc.name} - {_title(doc)}\n\n"
        f"_Status:_ {_meta_str(doc, 'status', 'draft')}  \n"
        f"_Path:_ `{doc.project}/{doc.relative_path}`\n\n" + doc.content.strip()
    ]

    if depth == "with_children" and doc.doc_type == "prd":
        stories = store.stories_of(doc)
        if stories:
            lines = [
                f"- **{s.name}** ({_meta_str(s, 'status', 'draft')}"
                f"{(' · ' + _meta_str(s, 'priority')) if _meta_str(s, 'priority') else ''})"
                f" - {_title(s)}"
                for s in stories
            ]
            parts.append("## Stories\n\n" + "\n".join(lines))
        else:
            parts.append("## Stories\n\n_No stories yet._")

    if depth == "with_parent" and doc.doc_type == "story":
        prd = store.prd_of(doc)
        if prd:
            parts.append(_prd_summary(prd))

    next_calls = _next_calls_section(doc, doc.project, key="targets").lstrip("\n")
    if next_calls:
        parts.append(next_calls)

    return [TextContent(type="text", text="\n\n".join(parts) + "\n")]
