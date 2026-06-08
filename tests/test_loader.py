"""Loader discovery rules — especially that a tools directory can safely be its
own git repo or contain a virtualenv without its internals being imported.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from textwrap import dedent

from remotetoolbox.config import ToolsConfig
from remotetoolbox.tooling import load_tools


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(body))


def test_loader_skips_hidden_vendor_and_private_files(tmp_path: Path) -> None:
    # A real tool that should load.
    _write(
        tmp_path / "weather" / "tool.py",
        """
        from remotetoolbox import tool

        @tool(description="Get weather.")
        def weather(city: str) -> str:
            return city
        """,
    )
    # A private helper (underscore) — must be skipped.
    _write(tmp_path / "weather" / "_helper.py", "VALUE = 1\n")

    # Files inside a nested git repo and a virtualenv that would register tools
    # IF imported. They must NOT be imported.
    for vendor, fn in [(".git", "junk_git"), (".venv", "junk_venv"), ("node_modules", "junk_node")]:
        _write(
            tmp_path / vendor / "sub" / "mod.py",
            f"""
            from remotetoolbox import tool

            @tool(description="junk")
            def {fn}() -> str:
                return "junk"
            """,
        )

    toolset = asyncio.run(load_tools(ToolsConfig(paths=[str(tmp_path)])))
    assert toolset.names() == ["weather"]


def test_loader_expands_user_home(tmp_path: Path, monkeypatch) -> None:
    # Point HOME at tmp so "~/mytools" resolves into the tmp tree.
    monkeypatch.setenv("HOME", str(tmp_path))
    _write(
        tmp_path / "mytools" / "t.py",
        """
        from remotetoolbox import tool

        @tool(description="Echo.")
        def echo(text: str) -> str:
            return text
        """,
    )
    toolset = asyncio.run(load_tools(ToolsConfig(paths=["~/mytools"])))
    assert "echo" in toolset.names()
