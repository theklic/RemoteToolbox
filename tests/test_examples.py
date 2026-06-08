"""Guard that the bundled example tools keep working as the framework evolves.

The examples are referenced from the README and docs as the copy-paste starting
point. If a change to the `@tool` API or the loader breaks them, this fails.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from remotetoolbox.config import ToolsConfig
from remotetoolbox.tooling import load_tools

ROOT = Path(__file__).resolve().parents[1]


def test_example_tools_load_and_run() -> None:
    examples = ROOT / "examples" / "tools"
    toolset = asyncio.run(load_tools(ToolsConfig(paths=[str(examples)])))

    names = set(toolset.names())
    expected = {"hello", "system_info", "disk_free", "now", "secret_greeting", "ping"}
    missing = expected - names
    assert not missing, f"Example tools failed to load: {sorted(missing)}"

    # Each loaded tool must render to a valid Ollama tool spec.
    for spec in toolset.ollama_tools():
        assert spec["type"] == "function"
        assert spec["function"]["name"]
        assert spec["function"]["parameters"]["type"] == "object"

    # The simplest tool actually runs through Toolset.call (covers sync + async path).
    assert "Sam" in asyncio.run(toolset.call("hello", {"name": "Sam"}))
    assert asyncio.run(toolset.call("ping", {"label": "pong"})) == "pong"
