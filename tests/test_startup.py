"""The one-time startup nudge that suggests versioning tools in ./tools."""

from __future__ import annotations

import logging
from pathlib import Path

from remotetoolbox.__main__ import _nudge_tools_versioning
from remotetoolbox.config import Config, ToolsConfig

_LOG = logging.getLogger("rtb-nudge-test")


def _make_tool(tools_dir: Path) -> None:
    (tools_dir / "hello").mkdir(parents=True)
    (tools_dir / "hello" / "tool.py").write_text("x = 1\n")


def _nudged(caplog) -> bool:
    return any("init-tools" in r.message for r in caplog.records)


def test_nudges_when_default_tools_is_unversioned(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    _make_tool(tmp_path / "tools")
    with caplog.at_level(logging.INFO, logger="rtb-nudge-test"):
        _nudge_tools_versioning(Config(), _LOG)
    assert _nudged(caplog)


def test_no_nudge_when_tools_is_its_own_git_repo(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    _make_tool(tmp_path / "tools")
    (tmp_path / "tools" / ".git").mkdir()
    with caplog.at_level(logging.INFO, logger="rtb-nudge-test"):
        _nudge_tools_versioning(Config(), _LOG)
    assert not _nudged(caplog)


def test_no_nudge_for_custom_tools_paths(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    _make_tool(tmp_path / "tools")
    cfg = Config(tools=ToolsConfig(paths=["~/rtb-tools"]))
    with caplog.at_level(logging.INFO, logger="rtb-nudge-test"):
        _nudge_tools_versioning(cfg, _LOG)
    assert not _nudged(caplog)


def test_no_nudge_before_any_tools_exist(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tools").mkdir()  # empty
    with caplog.at_level(logging.INFO, logger="rtb-nudge-test"):
        _nudge_tools_versioning(Config(), _LOG)
    assert not _nudged(caplog)
