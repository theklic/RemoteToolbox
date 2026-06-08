"""A slightly richer example: multiple tools in one file, an Optional argument,
a tool that reads a secret from the environment, and an async tool.

Copy to try:  cp -r examples/tools/system_info tools/system_info
"""

from __future__ import annotations

import os
import platform
import shutil
from datetime import datetime

from remotetoolbox import tool


@tool(description="Get basic information about the host machine.")
def system_info() -> dict:
    """Return OS, hostname, and CPU architecture as a small dict."""
    return {
        "system": platform.system(),
        "hostname": platform.node(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }


@tool(description="Report free disk space for a path (defaults to the root).")
def disk_free(path: str = "/") -> str:
    """Human-readable free / total disk space.

    path: Filesystem path to check. Defaults to the root filesystem.
    """
    usage = shutil.disk_usage(path)
    gb = 1024**3
    return f"{usage.free / gb:.1f} GB free of {usage.total / gb:.1f} GB at {path}"


@tool(description="Get the current local date and time.")
def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


@tool(description="Read a configured greeting prefix from the environment.")
def secret_greeting(name: str) -> str:
    """Show how a tool reads its own secret/config from the environment.

    Set GREETING_PREFIX in your .env. This value never gets committed.

    name: Who to greet.
    """
    prefix = os.environ.get("GREETING_PREFIX", "Hello")
    return f"{prefix}, {name}!"


@tool(description="Asynchronously wait, then confirm (demonstrates async tools).")
async def ping(label: str = "pong") -> str:
    """Async tools are supported — just declare the function `async def`.

    label: Text to echo back.
    """
    import asyncio

    await asyncio.sleep(0.05)
    return label
