"""tools/docs.py — get_agents_md, get_rules, get_pattern, get_skill tools."""

from __future__ import annotations

from mcp.types import TextContent, Tool

from loader import RulesStore
from metrics import args_to_doc_path
from search import RulesSearchEngine

DEFINITIONS: list[Tool] = [
    Tool(
        name="get_agents_md",
        description=(
            "Get the full agents.md for a project — identity, behavior rules, "
            "coding standards, security defaults. This is the primary entry "
            "point; load it first for any project."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {
                    "type": "string",
                    "description": "Project name. Use list_projects to discover values.",
                }
            },
            "required": ["project"],
        },
    ),
    Tool(
        name="get_rules",
        description=(
            "Get a specific reference doc for a project. Use for "
            "error-conventions, anti-patterns, glossary, or architecture."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "context": {
                    "type": "string",
                    "description": (
                        "Rule context to fetch. One of: "
                        "error-conventions, anti-patterns, glossary, architecture."
                    ),
                    "enum": [
                        "error-conventions",
                        "anti-patterns",
                        "glossary",
                        "architecture",
                    ],
                },
            },
            "required": ["project", "context"],
        },
    ),
    Tool(
        name="get_pattern",
        description=(
            "Get a canonical code pattern for a project (file under "
            "<project>/patterns/<name>.md). Use when GENERATING code — "
            "fetch the relevant pattern first. If you don't know the name, "
            'call list_rule_docs with doc_type="pattern".'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "pattern": {
                    "type": "string",
                    "description": (
                        "Pattern name without the .md extension. Use "
                        "list_rule_docs to discover available patterns."
                    ),
                },
            },
            "required": ["project", "pattern"],
        },
    ),
    Tool(
        name="get_skill",
        description=(
            "Get a step-by-step task workflow for a project (file under "
            "<project>/skills/<action>.md). Use when EXECUTING a multi-step "
            "task the user explicitly requested. If you don't know the name, "
            'call list_rule_docs with doc_type="skill".'
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Project name."},
                "skill": {
                    "type": "string",
                    "description": (
                        "Skill name without the .md extension. Use "
                        "list_rule_docs to discover available skills."
                    ),
                },
            },
            "required": ["project", "skill"],
        },
    ),
]

_NAMES = {"get_agents_md", "get_rules", "get_pattern", "get_skill"}

_CONTEXT_TO_PATH = {
    "error-conventions": "error-conventions.md",
    "anti-patterns": "anti-patterns.md",
    "glossary": "glossary.md",
    "architecture": "architecture.md",
}


async def dispatch(
    name: str,
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent] | None:
    if name not in _NAMES:
        return None

    if name == "get_agents_md":
        project = arguments.get("project", "").strip()
        ctx.doc_path = f"{project}/agents.md"  # type: ignore[attr-defined]
        doc = store.get(project, "agents.md")
        if not doc:
            ctx.status = "not_found"  # type: ignore[attr-defined]
            return [
                TextContent(
                    type="text",
                    text=(
                        f"agents.md not found for project '{project}'. "
                        "Call list_projects to see valid names."
                    ),
                )
            ]
        return [TextContent(type="text", text=doc.content)]

    if name == "get_rules":
        project = arguments.get("project", "").strip()
        context = arguments.get("context", "").strip()
        ctx.doc_path = args_to_doc_path("get_rules", arguments)  # type: ignore[attr-defined]
        relative_path = _CONTEXT_TO_PATH.get(context)
        if not relative_path:
            ctx.status = "error"  # type: ignore[attr-defined]
            return [
                TextContent(
                    type="text",
                    text=f"Unknown context '{context}'. Valid: {list(_CONTEXT_TO_PATH.keys())}",
                )
            ]
        doc = store.get(project, relative_path)
        if not doc:
            ctx.status = "not_found"  # type: ignore[attr-defined]
            return [
                TextContent(
                    type="text",
                    text=(
                        f"'{context}' doc not found for project '{project}'. "
                        "Call list_rule_docs to see what is available."
                    ),
                )
            ]
        return [TextContent(type="text", text=doc.content)]

    if name == "get_pattern":
        project = arguments.get("project", "").strip()
        pattern = arguments.get("pattern", "").strip()
        ctx.doc_path = args_to_doc_path("get_pattern", arguments)  # type: ignore[attr-defined]
        relative_path = f"patterns/{pattern}.md"
        doc = store.get(project, relative_path)
        if not doc:
            ctx.status = "not_found"  # type: ignore[attr-defined]
            return [
                TextContent(
                    type="text",
                    text=(
                        f"Pattern '{pattern}' not found for project '{project}'. "
                        'Call list_rule_docs with doc_type="pattern" to see '
                        "available patterns."
                    ),
                )
            ]
        return [TextContent(type="text", text=doc.content)]

    if name == "get_skill":
        project = arguments.get("project", "").strip()
        skill = arguments.get("skill", "").strip()
        ctx.doc_path = args_to_doc_path("get_skill", arguments)  # type: ignore[attr-defined]
        relative_path = f"skills/{skill}.md"
        doc = store.get(project, relative_path)
        if not doc:
            ctx.status = "not_found"  # type: ignore[attr-defined]
            return [
                TextContent(
                    type="text",
                    text=(
                        f"Skill '{skill}' not found for project '{project}'. "
                        'Call list_rule_docs with doc_type="skill" to see '
                        "available skills."
                    ),
                )
            ]
        return [TextContent(type="text", text=doc.content)]

    return None
