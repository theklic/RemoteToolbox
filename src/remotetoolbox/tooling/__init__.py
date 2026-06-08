"""Tool discovery and execution.

``load_tools`` scans the configured directories for ``@tool``-decorated
functions (and, optionally, connects to external MCP servers) and returns a
:class:`Toolset` the orchestrator can introspect and call.
"""

from __future__ import annotations

from .loader import Toolset, load_tools

__all__ = ["Toolset", "load_tools"]
