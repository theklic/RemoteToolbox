"""`remotetoolbox doctor` preflight checks (Ollama HTTP is injected, no network)."""

from __future__ import annotations

import asyncio

from remotetoolbox.config import ChatConfig, Config, TelegramConfig, ToolsConfig
from remotetoolbox.doctor import gather_checks


def _run(config, tags):
    async def tags_fn(host: str):
        if isinstance(tags, Exception):
            raise tags
        return tags

    return asyncio.run(gather_checks(config, tags_fn=tags_fn))


def _check(checks, needle):
    return next(c for c in checks if needle in c.label)


def test_all_ok_when_model_present_and_paths_exist(tmp_path):
    cfg = Config(tools=ToolsConfig(paths=[str(tmp_path)]))
    checks = _run(cfg, ["llama3.1:latest"])  # base name matches default model
    assert all(c.ok for c in checks), [(c.label, c.detail) for c in checks if not c.ok]


def test_flags_unreachable_ollama(tmp_path):
    cfg = Config(tools=ToolsConfig(paths=[str(tmp_path)]))
    checks = _run(cfg, RuntimeError("connection refused"))
    assert not _check(checks, "Ollama reachable").ok


def test_flags_missing_model(tmp_path):
    cfg = Config(tools=ToolsConfig(paths=[str(tmp_path)]))
    checks = _run(cfg, ["some-other-model:latest"])
    assert _check(checks, "Ollama reachable").ok
    assert not _check(checks, "Model").ok


def test_flags_missing_tools_path():
    cfg = Config(tools=ToolsConfig(paths=["/no/such/dir"]))
    checks = _run(cfg, ["llama3.1"])
    assert not _check(checks, "/no/such/dir").ok


def test_flags_empty_telegram_token_and_allowlist(tmp_path):
    cfg = Config(
        chat=ChatConfig(adapter="telegram", telegram=TelegramConfig(token="", allowed_users="")),
        tools=ToolsConfig(paths=[str(tmp_path)]),
    )
    checks = _run(cfg, ["llama3.1"])
    assert not _check(checks, "Telegram token").ok
    assert not _check(checks, "Telegram allowlist").ok
