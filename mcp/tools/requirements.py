"""tools/requirements.py - Requirements corpus MCP tools.

Tools:
 - playbook_list_requirements - catalogue PRDs/stories (never bodies)
 - playbook_start_requirement - PM authoring bootstrap (template + context + next id)

Fetching a single PRD/story is `playbook_get_doc(kind="requirement", name=<id>)`
in tools/docs.py - the requirements corpus is free once kinds share one tool.
"""

from __future__ import annotations

import re
from pathlib import Path

from mcp.types import TextContent, Tool

from loader import RuleDoc, RulesStore
from search import RulesSearchEngine

from . import PROJECT_PARAM_DESC
from .docs import _canonical_project

_MCP_DIR = Path(__file__).resolve().parent.parent
_TEMPLATES_DIR = _MCP_DIR / "templates"

DEFINITIONS: list[Tool] = [
    Tool(
        name="playbook_list_requirements",
        description=(
            "List PRDs and/or stories for a project. Returns id, title, status, "
            "priority, and a one-line summary - never bodies. Filter with "
            "type=, status=, or prd= (stories under a given PRD). Fetch a body "
            'with playbook_get_doc(kind="requirement", name=<id>).'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": PROJECT_PARAM_DESC,
                },
                "type": {
                    "type": "string",
                    "enum": ["prd", "story"],
                    "description": "Optional - restrict to PRDs or stories.",
                },
                "status": {
                    "type": "string",
                    "enum": ["draft", "approved", "shipped"],
                    "description": "Optional - filter by status.",
                },
                "prd": {
                    "type": "string",
                    "description": "Optional - list stories belonging to this PRD id.",
                },
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="playbook_start_requirement",
        description=(
            "Entry point for authoring a PRD or story (spec/PM work - for "
            "coding tasks use playbook_start_task). Returns the template, "
            "the next free id, glossary, architecture overview, guardrails, "
            "the matched write-* workflow, and suggested implementation "
            "targets from the standards corpus."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": PROJECT_PARAM_DESC,
                },
                "intent": {
                    "type": "string",
                    "description": (
                        "Free-form description of what to specify "
                        "(e.g. 'offline sync for saved articles')."
                    ),
                },
                "type": {
                    "type": "string",
                    "description": "What to author: prd (default) or story.",
                    "enum": ["prd", "story"],
                    "default": "prd",
                },
                "prd": {
                    "type": "string",
                    "description": "Required when type=story - parent PRD id.",
                },
            },
            "required": ["project", "intent"],
        },
    ),
]

_NAMES = {t.name for t in DEFINITIONS}

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def _meta_str(doc: RuleDoc, key: str, default: str = "") -> str:
    v = doc.metadata.get(key)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return default


def _title(doc: RuleDoc) -> str:
    t = _meta_str(doc, "title")
    if t:
        return t
    for line in doc.content.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
        if s and not s.startswith("---"):
            break
    return doc.name


def _summary(doc: RuleDoc, max_len: int = 160) -> str:
    desc = _meta_str(doc, "description")
    if desc:
        return desc[:max_len]
    for line in doc.content.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        return s[:max_len]
    return ""


def _find_req(store: RulesStore, req_id: str, project: str | None) -> RuleDoc | None:
    req_id = req_id.strip()
    projects = [project] if project else store.projects(corpus="requirements")
    for p in projects:
        doc = store.find_by_id("requirements", p, req_id)
        if doc:
            return doc
    return None


def _extract_sections(content: str, headings: list[str]) -> str:
    """Return named ## sections from content (case-insensitive heading match)."""
    wanted = {h.lower() for h in headings}
    parts = _SECTION_RE.split(content)
    # parts: [preamble, h1, body1, h2, body2, ...]
    out: list[str] = []
    i = 1
    while i + 1 < len(parts):
        heading, body = parts[i], parts[i + 1]
        if heading.strip().lower() in wanted:
            out.append(f"## {heading.strip()}\n\n{body.strip()}")
        i += 2
    return "\n\n".join(out)


def _prd_summary(prd: RuleDoc) -> str:
    title = _title(prd)
    status = _meta_str(prd, "status", "draft")
    sections = _extract_sections(prd.content, ["Problem", "Non-Goals"])
    return (
        f"### Parent PRD: `{prd.name}` - {title} ({status})\n\n"
        f"_Description:_ {_summary(prd)}\n\n"
        + (sections if sections else "_(no Problem / Non-Goals sections)_")
    )


def _next_id(store: RulesStore, project: str, kind: str) -> str:
    """Scan existing ids and return the next free PRD-NNN or ST-NNN."""
    prefix = "PRD-" if kind == "prd" else "ST-"
    nums: list[int] = []
    for doc in store.all_docs(corpus="requirements"):
        if doc.project != project:
            continue
        if doc.doc_type not in ("prd", "story"):
            continue
        rid = _meta_str(doc, "id") or doc.name
        if rid.startswith(prefix):
            try:
                nums.append(int(rid[len(prefix) :]))
            except ValueError:
                continue
    nxt = (max(nums) + 1) if nums else (1 if kind == "prd" else 100)
    return f"{prefix}{nxt:03d}" if kind == "prd" else f"{prefix}{nxt}"


def _load_template(kind: str) -> str:
    name = "PRD.md" if kind == "prd" else "STORY.md"
    path = _TEMPLATES_DIR / name
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"# {kind.upper()} template missing at mcp/templates/{name}\n"


def _suggest_targets(
    engine: RulesSearchEngine, project: str, intent: str, top_k: int = 5
) -> list[str]:
    results = engine.search(query=intent, project=project, corpus="standards", top_k=top_k)
    suggestions: list[str] = []
    for r in results:
        if r.doc_type == "pattern":
            suggestions.append(f"pattern:{Path(r.relative_path).stem}")
        elif r.doc_type == "skill":
            suggestions.append(f"skill:{Path(r.relative_path).stem}")
        elif r.doc_type == "language-rules":
            # languages/kotlin/testing.md → language:kotlin/testing
            parts = Path(r.relative_path).parts
            if len(parts) == 3:
                suggestions.append(f"language:{parts[1]}/{Path(parts[2]).stem}")
        elif r.doc_type == "workflow":
            suggestions.append(f"workflow:{Path(r.relative_path).stem}")
    # Dedupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


async def dispatch(
    name: str,
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent] | None:
    if name not in _NAMES:
        return None

    if name == "playbook_list_requirements":
        return _list_requirements(arguments, ctx, store)
    if name == "playbook_start_requirement":
        return _start_requirement(arguments, ctx, store, engine)
    return None


def _list_requirements(arguments: dict, ctx: object, store: RulesStore) -> list[TextContent]:
    project_raw = (arguments.get("project") or "").strip()
    type_filter = arguments.get("type") or None
    status_filter = arguments.get("status") or None
    prd_filter = (arguments.get("prd") or "").strip() or None

    if not project_raw:
        ctx.status = "error"
        return [TextContent(type="text", text="`project` is required.")]

    known = list(store.projects(corpus="requirements")) + list(
        store.projects(corpus="standards")
    )
    known_unique = list(dict.fromkeys(known))
    project = _canonical_project(project_raw, known_unique)
    if project is None:
        ctx.status = "not_found"
        listing = "\n".join(f"- {p}" for p in known_unique) or "(none)"
        return [
            TextContent(
                type="text",
                text=(
                    f"Project '{project_raw}' not found. "
                    "`project` must be the basename of your current workspace "
                    f"directory. Available:\n{listing}"
                ),
            )
        ]

    docs = [
        d
        for d in store.for_project(project, corpus="requirements")
        if d.doc_type in ("prd", "story")
    ]

    if type_filter:
        docs = [d for d in docs if d.doc_type == type_filter]

    if status_filter:
        docs = [d for d in docs if _meta_str(d, "status", "draft") == status_filter]

    if prd_filter:
        prd = store.find_by_id("requirements", project, prd_filter)
        if not prd or prd.doc_type != "prd":
            ctx.status = "not_found"
            return [
                TextContent(
                    type="text",
                    text=(
                        f"PRD '{prd_filter}' not found in {project}. "
                        "Call playbook_list_requirements."
                    ),
                )
            ]
        docs = store.stories_of(prd)

    if not docs:
        ctx.status = "empty"
        return [
            TextContent(
                type="text",
                text=f"No requirements matched for project '{project}'.",
            )
        ]

    lines: list[str] = []
    for d in sorted(docs, key=lambda x: (x.doc_type, x.name)):
        status = _meta_str(d, "status", "draft")
        priority = _meta_str(d, "priority")
        pri = f" · {priority}" if priority else ""
        lines.append(
            f"- **{d.name}** ({d.doc_type}, {status}{pri}) - *{_title(d)}*\n  {_summary(d)}"
        )
    return [TextContent(type="text", text="\n".join(lines))]


def _start_requirement(
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent]:
    project_raw = (arguments.get("project") or "").strip()
    intent = (arguments.get("intent") or "").strip()
    kind = (arguments.get("type") or "prd").strip()
    parent_prd = (arguments.get("prd") or "").strip()

    if not project_raw or not intent:
        ctx.status = "error"
        return [
            TextContent(
                type="text",
                text="Both `project` and `intent` are required.",
            )
        ]

    known_standards = list(store.projects(corpus="standards"))
    project = _canonical_project(project_raw, known_standards)
    if project is None:
        ctx.status = "not_found"
        listing = "\n".join(f"- {p}" for p in known_standards) or "(none)"
        return [
            TextContent(
                type="text",
                text=(
                    f"Project '{project_raw}' not found under standards/. "
                    "`project` must be the basename of your current workspace "
                    f"directory. Available:\n{listing}"
                ),
            )
        ]

    if kind == "story" and not parent_prd:
        ctx.status = "error"
        return [
            TextContent(
                type="text",
                text="`prd` is required when type=story.",
            )
        ]

    if kind == "story":
        prd = store.find_by_id("requirements", project, parent_prd)
        if not prd or prd.doc_type != "prd":
            ctx.status = "not_found"
            return [
                TextContent(
                    type="text",
                    text=(
                        f"Parent PRD '{parent_prd}' not found in {project}. "
                        "Call playbook_list_requirements."
                    ),
                )
            ]

    ctx.query = intent
    next_id = _next_id(store, project, kind)
    ctx.requirement_id = next_id

    template = _load_template(kind)
    glossary = store.get(project, "core/glossary.md", corpus="standards")
    overview = store.get(project, "architecture/overview.md", corpus="standards")
    guard = store.get(project, "core/guardrails.md", corpus="standards")

    wf_name = "write-prd" if kind == "prd" else "write-story"
    workflow = store.get(project, f"workflows/{wf_name}.md", corpus="requirements")

    suggestions = _suggest_targets(engine, project, intent)

    parts: list[str] = [
        f"# playbook_start_requirement - {project}\n\n"
        f"_Intent:_ {intent}  \n"
        f"_Type:_ {kind}  \n"
        f"_Next id:_ **`{next_id}`**"
        + (f"  \n_Parent PRD:_ `{parent_prd}`" if parent_prd else "")
        + "\n"
    ]

    parts.append(f"## Template\n\n```markdown\n{template.rstrip()}\n```")

    if glossary:
        parts.append("## Glossary\n\n" + glossary.content.strip())
    if overview:
        parts.append("## Architecture overview\n\n" + overview.content.strip())
    if guard:
        parts.append(
            "## Guardrails (do not spec anything these forbid)\n\n" + guard.content.strip()
        )
    if workflow:
        parts.append(f"## Matched workflow: `{workflow.name}`\n\n" + workflow.content.strip())
    else:
        parts.append(
            f"## Matched workflow\n\n"
            f"_No requirements/{project}/workflows/{wf_name}.md yet - "
            "create it so PMs get a consistent authoring flow._"
        )

    if suggestions:
        joined = ", ".join(suggestions)
        parts.append(
            "## Suggested `targets:` (edit before committing)\n\n"
            f"`targets: [{joined}]`\n\n"
            "These came from a search over standards - keep what fits, "
            "drop the rest."
        )
    else:
        parts.append(
            "## Suggested `targets:`\n\n"
            "_No strong matches - call "
            f'`playbook_search_docs(project="{project}", corpus="standards", '
            'query="<keywords>")` to find candidates._'
        )

    parts.append(
        "---\n\n## Next Calls\n\n"
        f'- `playbook_search_docs(project="{project}", corpus="standards", '
        f'query="{intent}")` - find more targets\n'
        f'- `playbook_list_requirements(project="{project}")` - see existing PRDs/stories\n'
    )

    return [TextContent(type="text", text="\n\n".join(parts) + "\n")]
