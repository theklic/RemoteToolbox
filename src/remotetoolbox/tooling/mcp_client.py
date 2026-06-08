"""Optional: connect to existing external MCP servers and surface their tools.

This lets you reuse the growing ecosystem of MCP servers (filesystem, GitHub,
home automation, …) alongside your own native ``@tool`` functions. Requires the
``mcp`` extra::

    pip install -e ".[mcp]"

Each configured server is launched over stdio; its advertised tools are wrapped
as :class:`ToolSpec` objects whose ``func`` proxies the call back over MCP.

This is intentionally thin. If you only use native Python tools you never import
this module and never need the ``mcp`` dependency.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any

from ..config import MCPServerConfig
from ..registry import ToolSpec

log = logging.getLogger(__name__)


class MCPManager:
    """Manages the lifecycle of one or more stdio MCP server connections."""

    def __init__(self, servers: list[MCPServerConfig]) -> None:
        self.servers = servers
        self._stack = AsyncExitStack()
        self._sessions: dict[str, Any] = {}

    async def connect(self) -> list[ToolSpec]:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "MCP servers configured but the 'mcp' package is not installed. "
                "Run: pip install -e \".[mcp]\""
            ) from exc

        specs: list[ToolSpec] = []
        for server in self.servers:
            params = StdioServerParameters(
                command=server.command, args=server.args, env=server.env or None
            )
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._sessions[server.name] = session

            listed = await session.list_tools()
            for mcp_tool in listed.tools:
                specs.append(self._wrap(server.name, session, mcp_tool))
            log.info("Connected MCP server %r with %d tool(s).", server.name, len(listed.tools))
        return specs

    def _wrap(self, server_name: str, session: Any, mcp_tool: Any) -> ToolSpec:
        async def _call(**arguments: Any) -> str:
            result = await session.call_tool(mcp_tool.name, arguments)
            # MCP returns content blocks; concatenate the text parts.
            parts = [getattr(c, "text", "") for c in getattr(result, "content", [])]
            return "\n".join(p for p in parts if p) or "Done."

        return ToolSpec(
            name=mcp_tool.name,
            description=getattr(mcp_tool, "description", "") or mcp_tool.name,
            parameters=getattr(mcp_tool, "inputSchema", None) or {"type": "object", "properties": {}},
            func=_call,
            is_async=True,
            source=f"mcp:{server_name}",
        )

    async def aclose(self) -> None:
        await self._stack.aclose()
