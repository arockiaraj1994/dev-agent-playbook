"""tools/projects.py — list_projects and list_rule_docs tools."""

from __future__ import annotations

from mcp.types import TextContent, Tool

from loader import RuleDoc, RulesStore
from search import RulesSearchEngine

DEFINITIONS: list[Tool] = [
    Tool(
        name="list_projects",
        description=(
            "List all projects available in the rule docs repository. "
            "Call this first when you don't know the project name."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
    Tool(
        name="list_rule_docs",
        description=(
            "List rule documents for a project, optionally filtered by type. "
            "Returns names, doc types, paths, titles, and short summaries — "
            "use this to discover what's available BEFORE calling get_pattern, "
            "get_skill, or get_rules. Cheaper than search_rules when you "
            "already know the project."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name. Use list_projects to discover values.",
                },
                "doc_type": {
                    "type": "string",
                    "description": (
                        "Optional filter. One of: agents, architecture, "
                        "error-conventions, anti-patterns, glossary, "
                        "pattern, skill."
                    ),
                    "enum": [
                        "agents",
                        "architecture",
                        "error-conventions",
                        "anti-patterns",
                        "glossary",
                        "pattern",
                        "skill",
                    ],
                },
            },
            "required": ["project"],
        },
    ),
]

_NAMES = {"list_projects", "list_rule_docs"}


def _doc_title(doc: RuleDoc) -> str:
    t = doc.metadata.get("title")
    if isinstance(t, str) and t.strip():
        return t.strip()
    for line in doc.content.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
        if s and not s.startswith("---"):
            break
    return doc.name


def _doc_summary(doc: RuleDoc, max_len: int = 200) -> str:
    desc = doc.metadata.get("description")
    if isinstance(desc, str) and desc.strip():
        return desc.strip()[:max_len]
    for line in doc.content.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("---"):
            continue
        if s.startswith(">"):
            continue
        return s[:max_len]
    return ""


async def dispatch(
    name: str,
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent] | None:
    if name not in _NAMES:
        return None

    if name == "list_projects":
        projects = store.projects()
        if not projects:
            ctx.status = "empty"  # type: ignore[attr-defined]
            return [TextContent(type="text", text="No projects found in the rules repository.")]
        lines = "\n".join(f"- {p}" for p in projects)
        return [TextContent(type="text", text=f"Available projects:\n{lines}")]

    if name == "list_rule_docs":
        project = arguments.get("project", "").strip()
        if project not in store.projects():
            ctx.status = "not_found"  # type: ignore[attr-defined]
            return [
                TextContent(
                    type="text",
                    text=f"Project '{project}' not found. Call list_projects to see valid names.",
                )
            ]
        doc_type = arguments.get("doc_type")
        docs = store.of_type(project, doc_type) if doc_type else store.for_project(project)
        if not docs:
            ctx.status = "empty"  # type: ignore[attr-defined]
            type_clause = f" of type '{doc_type}'" if doc_type else ""
            return [
                TextContent(
                    type="text",
                    text=f"No rule docs{type_clause} for project '{project}'.",
                )
            ]

        def sort_key(d: RuleDoc) -> tuple[str, str]:
            return (d.doc_type, d.relative_path)

        lines = []
        for d in sorted(docs, key=sort_key):
            title = _doc_title(d)
            summary = _doc_summary(d)
            lines.append(
                f"- **{d.relative_path}** ({d.doc_type}) — *{title}*"
                + (f"\n  {summary}" if summary else "")
            )
        return [TextContent(type="text", text="\n".join(lines))]

    return None
