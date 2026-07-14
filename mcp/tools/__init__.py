"""tools/ - MCP tool modules.

Every tool this server exposes only reads markdown from disk: nothing writes,
mutates, or reaches the network (gate scripts are shown, never executed). So a
single annotation set applies to all of them, and server.list_tools() stamps it
on centrally rather than each module repeating it.
"""

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

# One shared description for the `project` parameter - every tool requires it,
# so agents see identical wording everywhere.
PROJECT_PARAM_DESC = (
    "Basename of the user's current workspace directory "
    "(e.g. cwd .../NexRe → 'nexre'; case-insensitive match to a standards/ "
    "folder). Do not substitute a different project."
)

__all__ = ["PROJECT_PARAM_DESC", "READ_ONLY"]
