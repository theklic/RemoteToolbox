"""RemoteToolbox — chat with your own local tools from anywhere.

The public surface for *tool authors* is intentionally tiny: import ``tool`` and
decorate a function. Everything else is framework internals.

    from remotetoolbox import tool

    @tool(description="Say hello.")
    def hello(name: str) -> str:
        return f"Hello, {name}!"
"""

from __future__ import annotations

from .registry import ToolSpec, tool

__all__ = ["tool", "ToolSpec", "__version__"]

__version__ = "0.1.0"
