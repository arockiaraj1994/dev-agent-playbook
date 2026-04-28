"""tools/search_tool.py — search_rules tool."""

from __future__ import annotations

from mcp.types import TextContent, Tool

from loader import RulesStore
from search import RulesSearchEngine

DEFINITIONS: list[Tool] = [
    Tool(
        name="search_rules",
        description=(
            "BM25 full-text search across all rule docs. Use when you don't "
            "know which doc to fetch, or for cross-cutting questions. "
            "Headings and frontmatter title/tags are weighted 2× over body. "
            "Returns ranked snippets with source path and parent heading."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query — keywords or natural language.",
                },
                "project": {
                    "type": "string",
                    "description": "Optional — restrict search to one project.",
                },
                "doc_type": {
                    "type": "string",
                    "description": 'Optional — restrict to a doc type (e.g. "pattern").',
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
                "top_k": {
                    "type": "integer",
                    "description": "Max results to return. Default: 10.",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["query"],
        },
    ),
]

_NAMES = {"search_rules"}


async def dispatch(
    name: str,
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent] | None:
    if name not in _NAMES:
        return None

    query = arguments.get("query", "").strip()
    project = arguments.get("project") or None
    doc_type = arguments.get("doc_type") or None
    try:
        top_k = int(arguments.get("top_k", 10))
    except (TypeError, ValueError):
        top_k = 10
    top_k = max(1, min(50, top_k))

    if not query:
        ctx.status = "error"  # type: ignore[attr-defined]
        return [TextContent(type="text", text="Query must not be empty.")]

    ctx.query = query  # type: ignore[attr-defined]
    results = engine.search(query=query, project=project, doc_type=doc_type, top_k=top_k)
    if not results:
        ctx.status = "empty"  # type: ignore[attr-defined]
        return [TextContent(type="text", text=f"No results found for query: '{query}'")]

    top = results[0]
    ctx.top_result_path = f"{top.project}/{top.relative_path}"  # type: ignore[attr-defined]
    ctx.top_result_score = top.score  # type: ignore[attr-defined]

    lines = []
    for i, r in enumerate(results, 1):
        heading_str = f" — under heading: *{r.heading}*" if r.heading else ""
        lines.append(
            f"### {i}. {r.project}/{r.relative_path}  "
            f"(type: {r.doc_type}, score: {r.score}){heading_str}\n\n"
            f"{r.snippet}\n"
        )
    return [TextContent(type="text", text="\n---\n".join(lines))]
