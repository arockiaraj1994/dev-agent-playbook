"""tools/projects.py — list_projects tool.

Doc discovery lives in `find_rules` (tools/search_tool.py); this module only
answers "what projects exist?".
"""

from __future__ import annotations

from mcp.types import TextContent, Tool

from loader import RulesStore
from search import RulesSearchEngine

DEFINITIONS: list[Tool] = [
    Tool(
        name="list_projects",
        description=(
            "Lists the project names available in the rule docs repository. "
            "If you already know the project, skip this and call start_task."
        ),
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
        },
    ),
]

_NAMES = {"list_projects"}


async def dispatch(
    name: str,
    arguments: dict,
    ctx: object,
    store: RulesStore,
    engine: RulesSearchEngine,
) -> list[TextContent] | None:
    if name not in _NAMES:
        return None

    projects = store.projects()
    if not projects:
        ctx.status = "empty"  # type: ignore[attr-defined]
        return [TextContent(type="text", text="No projects found in the rules repository.")]
    lines = "\n".join(f"- {p}" for p in projects)
    return [TextContent(type="text", text=f"Available projects:\n{lines}")]
