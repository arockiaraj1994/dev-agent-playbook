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

__all__ = ["READ_ONLY"]
