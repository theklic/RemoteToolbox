"""Discover user tools from disk and bundle them into a :class:`Toolset`.

Discovery rule: every ``*.py`` file under a configured tools directory is
imported (excluding ``_``-prefixed files and ``__pycache__``). Importing the
module runs the ``@tool`` decorators, which populate the global registry; we
snapshot that registry after each scan.

Tools are loaded by file path (not as installed packages) so users can just drop
files into ``./tools`` without packaging anything.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import ToolsConfig
from ..registry import REGISTRY, ToolSpec, clear_registry

log = logging.getLogger(__name__)


@dataclass
class Toolset:
    """The set of tools available to the agent, plus how to call them."""

    specs: dict[str, ToolSpec] = field(default_factory=dict)
    call_timeout: float | None = None  # seconds; None/0 = no limit
    _mcp: Any = None  # optional MCPManager, lazily created

    def ollama_tools(self) -> list[dict[str, Any]]:
        return [spec.to_ollama_tool() for spec in self.specs.values()]

    def names(self) -> list[str]:
        return list(self.specs)

    async def call(self, name: str, arguments: dict[str, Any]) -> str:
        """Invoke a tool by name and return a string result for the model.

        Errors are caught and returned as text so one failing tool can't crash
        the agent — the model sees the error and can recover or apologise.
        """
        spec = self.specs.get(name)
        if spec is None:
            return f"Error: no tool named {name!r}. Available: {', '.join(self.specs) or 'none'}."
        try:
            if spec.is_async:
                call = spec.func(**arguments)
            else:
                # Run sync tools off the event loop so blocking I/O doesn't stall chat.
                call = asyncio.to_thread(spec.func, **arguments)
            if self.call_timeout and self.call_timeout > 0:
                result = await asyncio.wait_for(call, self.call_timeout)
            else:
                result = await call
            return _stringify(result)
        except asyncio.TimeoutError:
            # A timed-out sync tool's thread keeps running (it can't be killed);
            # we just stop waiting for it. Async tools are cancelled cleanly.
            log.warning("Tool %s timed out after %ss", name, self.call_timeout)
            return f"Error: tool {name} timed out after {self.call_timeout:g}s."
        except TypeError as exc:
            return f"Error calling {name}: bad arguments ({exc})."
        except Exception as exc:  # noqa: BLE001 - surface any tool error to the model
            log.exception("Tool %s raised", name)
            return f"Error: tool {name} failed: {exc}"

    async def aclose(self) -> None:
        if self._mcp is not None:
            await self._mcp.aclose()


def _stringify(result: Any) -> str:
    if result is None:
        return "Done."
    if isinstance(result, str):
        return result
    try:
        import json

        return json.dumps(result, default=str, ensure_ascii=False)
    except TypeError:
        return str(result)


def _import_file(path: Path) -> None:
    """Import a standalone .py file so its @tool decorators run.

    The file's own directory is **appended** to ``sys.path`` so a tool can import
    a sibling private helper (e.g. ``from _client import ...``). We append rather
    than prepend so a tool-directory file can't shadow a stdlib / site-packages
    module of the same name (e.g. a ``secrets.py`` next to a tool). Helper module
    names are resolved by bare name and cached globally, so keep them unique
    across tool folders (prefix them, e.g. ``_weather_client.py``).
    """
    module_name = f"rtb_tool_{path.stem}_{abs(hash(path)) & 0xFFFFFF:x}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        log.warning("Could not create import spec for %s", path)
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    parent = str(path.parent)
    if parent not in sys.path:
        sys.path.append(parent)
        _ADDED_SYSPATH.append(parent)

    spec.loader.exec_module(module)


# Tool dirs we appended to sys.path, so a later load_tools() can drop the ones it
# added before (avoids unbounded growth across reloads). We never remove entries
# we didn't add — and we keep this scan's entries on the path so tools can import
# their siblings lazily, at call time.
_ADDED_SYSPATH: list[str] = []


def _reset_syspath() -> None:
    for p in _ADDED_SYSPATH:
        try:
            sys.path.remove(p)
        except ValueError:
            pass
    _ADDED_SYSPATH.clear()


# Directories whose contents are never tool files. Skipping these lets a tools
# directory safely be its own git repo (or contain a virtualenv / vendored deps)
# without the loader trying to import their internals.
_SKIP_DIRS = frozenset(
    {
        "__pycache__",
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "env",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".tox",
        "site-packages",
    }
)


def _skipped(rel: Path) -> bool:
    """True if a discovered file should be ignored: a private (``_``-prefixed)
    file, or anything inside a hidden (``.git``, ``.venv``, …) or vendored dir."""
    if rel.name.startswith("_"):
        return True
    return any(part.startswith(".") or part in _SKIP_DIRS for part in rel.parts[:-1])


def _discover_dir(directory: Path) -> None:
    if not directory.exists():
        log.warning("Tools directory %s does not exist (skipping).", directory)
        return
    for path in sorted(directory.rglob("*.py")):
        if _skipped(path.relative_to(directory)):
            continue
        try:
            _import_file(path)
            log.debug("Loaded tool module %s", path)
        except Exception:  # noqa: BLE001
            log.exception("Failed to import tool file %s (skipping)", path)


async def load_tools(config: ToolsConfig) -> Toolset:
    """Scan configured paths (and MCP servers) and return a ready Toolset."""
    clear_registry()
    _reset_syspath()  # drop tool dirs a previous scan added before re-scanning
    for raw_path in config.paths:
        _discover_dir(Path(raw_path).expanduser())

    specs = dict(REGISTRY)  # snapshot
    toolset = Toolset(specs=specs, call_timeout=config.call_timeout)

    if config.mcp_servers:
        from .mcp_client import MCPManager  # optional dependency

        manager = MCPManager(config.mcp_servers)
        mcp_specs = await manager.connect()
        for spec in mcp_specs:
            if spec.name in toolset.specs:
                log.warning("MCP tool %r shadows a local tool; keeping local one.", spec.name)
                continue
            toolset.specs[spec.name] = spec
        toolset._mcp = manager

    log.info("Loaded %d tool(s): %s", len(toolset.specs), ", ".join(toolset.specs) or "(none)")
    return toolset
