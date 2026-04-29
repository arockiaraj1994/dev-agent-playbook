"""tools/docs.py — Doc-fetch MCP tools.

Tools defined here:
  - get_agents_md         — identity / behavior doc
  - get_guardrails        — always-on rules (guardrails + definition-of-done)
  - get_index             — auto-generated trigger map
  - get_architecture      — overview or named ADR
  - get_language_rules    — per-language standards / testing / anti-patterns
  - get_pattern           — canonical noun-named code pattern
  - get_skill             — verb-noun playbook
  - get_workflow          — task-driven flow (new-feature, bug-fix, ...)
  - get_gate              — gate README + executable script listing

Each return body is the doc content plus, if the doc declares `see_also`
in frontmatter, a `## Next Calls` section that names the exact tool calls
the agent should make next. This is the AI-agent-friendly contract: every
fetch is self-describing and chains forward.
"""

from __future__ import annotations

from mcp.types import TextContent, Tool

from loader import RuleDoc, RulesStore
from search import RulesSearchEngine

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

_LANGUAGE_DOCS = ["standards", "testing", "anti-patterns"]
_WORKFLOW_NAMES = ["new-feature", "bug-fix", "security-fix", "refactor"]


DEFINITIONS: list[Tool] = [
    Tool(
        name="get_agents_md",
        description=(
            "Call this when you need the project's identity / behavior doc "
            "(AGENTS.md). Returns the top-level AGENTS.md content."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name. Use list_projects to discover values.",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="get_guardrails",
        description=(
            "Call this at the start of every task and any time you need to "
            "re-check the always-on rules. Returns core/guardrails.md "
            "concatenated with core/definition-of-done.md."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="get_index",
        description=(
            "Call this to browse the trigger map (task-phrase → doc paths) "
            "without committing to a specific task. Returns the auto-generated "
            "INDEX.md."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="get_architecture",
        description=(
            "Call this when you need the system overview or a specific "
            "Architectural Decision Record. Omit `name` for the overview; "
            "pass `name=\"0007-<slug>\"` for a specific ADR."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "name": {
                    "type": "string",
                    "description": (
                        "Optional. ADR slug under architecture/decisions/ "
                        "(without .md). Omit for architecture/overview.md."
                    ),
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="get_language_rules",
        description=(
            "Call this whenever you are about to write or modify code in a "
            "specific language. Returns languages/<language>/<doc>.md."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "language": {
                    "type": "string",
                    "description": (
                        "Language code matching a folder under languages/ "
                        "(e.g. java, typescript, python, kotlin, sql, "
                        "shell-yaml). Use list_rule_docs with "
                        "doc_type=\"language-rules\" to see what is available."
                    ),
                },
                "doc": {
                    "type": "string",
                    "description": (
                        "Which language doc to fetch. Default: standards."
                    ),
                    "enum": _LANGUAGE_DOCS,
                    "default": "standards",
                },
            },
            "required": ["project", "language"],
        },
    ),
    Tool(
        name="get_pattern",
        description=(
            "Call this when GENERATING code that should follow a canonical "
            "pattern. Returns patterns/<name>.md. If you don't know the "
            "name, call list_rule_docs with doc_type=\"pattern\"."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "pattern": {
                    "type": "string",
                    "description": "Pattern name without .md.",
                },
            },
            "required": ["project", "pattern"],
        },
    ),
    Tool(
        name="get_skill",
        description=(
            "Call this when EXECUTING a verb-noun playbook (e.g. add-route, "
            "debug-route). Returns skills/<name>.md."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "skill": {
                    "type": "string",
                    "description": "Skill name without .md.",
                },
            },
            "required": ["project", "skill"],
        },
    ),
    Tool(
        name="get_workflow",
        description=(
            "Call this when the user's task matches a task-driven flow "
            "(new-feature, bug-fix, security-fix, refactor). Returns "
            "workflows/<name>.md, which lists the gates that close the task."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "name": {
                    "type": "string",
                    "description": "Workflow name without .md.",
                    "enum": _WORKFLOW_NAMES,
                },
            },
            "required": ["project", "name"],
        },
    ),
    Tool(
        name="get_gate",
        description=(
            "Call this before claiming a task complete, to verify "
            "definition-of-done. Omit `name` to get the gate README plus a "
            "listing of executable scripts. Pass `name=\"verify-<lang>\"` to "
            "see the script's path and first lines (the script is NOT "
            "executed by the server)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "name": {
                    "type": "string",
                    "description": (
                        "Optional. Script basename without .sh "
                        "(e.g. verify-java)."
                    ),
                },
            },
            "required": ["project"],
        },
    ),
]


_NAMES = {t.name for t in DEFINITIONS}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _next_calls_section(doc: RuleDoc, project: str) -> str:
    """Render a `## Next Calls` block from `see_also` frontmatter.

    `see_also` entries are of the form `<kind>:<name>`, where kind is one of:
        pattern, skill, workflow, gate, language, architecture, ref
    """
    raw = doc.metadata.get("see_also") or []
    if not isinstance(raw, list) or not raw:
        return ""

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

    if not lines:
        return ""
    return "\n\n---\n\n## Next Calls\n\n" + "\n".join(lines) + "\n"


def _format_call(kind: str, project: str, name: str) -> str | None:
    if kind == "pattern":
        return f"`get_pattern(project=\"{project}\", pattern=\"{name}\")` — pattern `{name}`"
    if kind == "skill":
        return f"`get_skill(project=\"{project}\", skill=\"{name}\")` — skill `{name}`"
    if kind == "workflow":
        return f"`get_workflow(project=\"{project}\", name=\"{name}\")` — workflow `{name}`"
    if kind == "gate":
        suffix = "" if name in ("", "gate") else f", name=\"{name}\""
        return f"`get_gate(project=\"{project}\"{suffix})` — gate `{name}`"
    if kind == "language":
        # `language:java/standards` or `language:java`
        if "/" in name:
            lang, doc = name.split("/", 1)
            return (
                f"`get_language_rules(project=\"{project}\", language=\"{lang}\", "
                f"doc=\"{doc}\")` — {lang} {doc}"
            )
        return (
            f"`get_language_rules(project=\"{project}\", language=\"{name}\")` "
            f"— {name} standards"
        )
    if kind == "architecture":
        if name in ("", "overview"):
            return f"`get_architecture(project=\"{project}\")` — overview"
        return (
            f"`get_architecture(project=\"{project}\", name=\"{name}\")` — ADR `{name}`"
        )
    return None


def _render(doc: RuleDoc, project: str) -> str:
    return doc.content + _next_calls_section(doc, project)


def _not_found(message: str) -> list[TextContent]:
    return [TextContent(type="text", text=message)]


def _set_path(ctx: object, path: str | None) -> None:
    setattr(ctx, "doc_path", path)


def _set_status(ctx: object, status: str) -> None:
    setattr(ctx, "status", status)


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

    if name == "get_agents_md":
        return _fetch(store, ctx, project, "AGENTS.md", "AGENTS.md")

    if name == "get_guardrails":
        return _get_guardrails(store, ctx, project)

    if name == "get_index":
        return _fetch(store, ctx, project, "INDEX.md", "INDEX.md (have you run validate-rules.py?)")

    if name == "get_architecture":
        adr = (arguments.get("name") or "").strip()
        if adr:
            rel = f"architecture/decisions/{adr}.md"
            return _fetch(store, ctx, project, rel, f"ADR '{adr}'")
        return _fetch(store, ctx, project, "architecture/overview.md", "architecture/overview.md")

    if name == "get_language_rules":
        language = (arguments.get("language") or "").strip()
        doc = (arguments.get("doc") or "standards").strip()
        if not language:
            _set_status(ctx, "error")
            return _not_found("Argument `language` is required.")
        if doc not in _LANGUAGE_DOCS:
            _set_status(ctx, "error")
            return _not_found(f"`doc` must be one of {_LANGUAGE_DOCS}; got '{doc}'.")
        rel = f"languages/{language}/{doc}.md"
        return _fetch(store, ctx, project, rel, f"{language}/{doc}")

    if name == "get_pattern":
        pat = (arguments.get("pattern") or "").strip()
        return _fetch(store, ctx, project, f"patterns/{pat}.md", f"pattern '{pat}'")

    if name == "get_skill":
        skill = (arguments.get("skill") or "").strip()
        return _fetch(store, ctx, project, f"skills/{skill}.md", f"skill '{skill}'")

    if name == "get_workflow":
        wf = (arguments.get("name") or "").strip()
        return _fetch(store, ctx, project, f"workflows/{wf}.md", f"workflow '{wf}'")

    if name == "get_gate":
        return _get_gate(store, ctx, project, (arguments.get("name") or "").strip())

    return None


# ---------------------------------------------------------------------------
# Per-tool implementations
# ---------------------------------------------------------------------------


def _fetch(
    store: RulesStore,
    ctx: object,
    project: str,
    relative_path: str,
    label: str,
) -> list[TextContent]:
    _set_path(ctx, f"{project}/{relative_path}")
    doc = store.get(project, relative_path)
    if not doc:
        _set_status(ctx, "not_found")
        return _not_found(
            f"{label} not found for project '{project}' "
            f"(expected at {relative_path}). "
            "Call list_rule_docs to see what is available."
        )
    return [TextContent(type="text", text=_render(doc, project))]


def _get_guardrails(
    store: RulesStore, ctx: object, project: str
) -> list[TextContent]:
    _set_path(ctx, f"{project}/core/guardrails.md+definition-of-done.md")
    guard = store.get(project, "core/guardrails.md")
    dod = store.get(project, "core/definition-of-done.md")
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


def _get_gate(
    store: RulesStore, ctx: object, project: str, name: str
) -> list[TextContent]:
    gate = store.get(project, "gates/README.md")
    if not gate:
        _set_status(ctx, "not_found")
        _set_path(ctx, f"{project}/gates/README.md")
        return _not_found(
            f"No gates/README.md for project '{project}'."
        )
    scripts = gate.metadata.get("gate_scripts") or []

    if not name:
        _set_path(ctx, f"{project}/gates/README.md")
        listing = (
            "\n\n## Available scripts\n\n"
            + "\n".join(f"- `gates/scripts/{s}`" for s in scripts)
            if scripts
            else "\n\n_No executable scripts under gates/scripts/._\n"
        )
        return [TextContent(type="text", text=gate.content + listing)]

    # Specific script requested — locate it among gate_scripts.
    script_filename = name if name.endswith(".sh") else f"{name}.sh"
    _set_path(ctx, f"{project}/gates/scripts/{script_filename}")
    if script_filename not in scripts:
        _set_status(ctx, "not_found")
        return _not_found(
            f"Gate script '{script_filename}' not found for project '{project}'. "
            f"Available: {scripts or '[]'}."
        )
    # Show metadata, not contents — server is read-only and never executes.
    text = (
        f"# Gate: {script_filename}\n\n"
        f"Path: `{project}/gates/scripts/{script_filename}`\n\n"
        "The MCP server does not execute gate scripts. To run it locally:\n\n"
        f"```\nbash {project}/gates/scripts/{script_filename}\n```\n\n"
        "See the gate README for what this script enforces:\n\n"
        + gate.content
    )
    return [TextContent(type="text", text=text)]
