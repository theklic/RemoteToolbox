"""TranscriptLog: per-chat JSONL chat-history logging used by the Telegram adapter.

These don't need the `telegram` extra — the logger is a standalone helper.
"""

from __future__ import annotations

import json

from remotetoolbox.chat.transcript import TranscriptLog
from remotetoolbox.config import TelegramConfig


def _read(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_disabled_when_directory_blank(tmp_path):
    log = TranscriptLog("")
    assert log.enabled is False
    log.record("123", "in", "hi")  # no-op, must not raise or create anything
    assert list(tmp_path.iterdir()) == []


def test_records_turns_to_per_chat_file(tmp_path):
    log = TranscriptLog(str(tmp_path / "telegram"))
    assert log.enabled is True
    log.record("123", "in", "hello", user_id=42)
    log.record("123", "out", "hi there")

    entries = _read(tmp_path / "telegram" / "123.jsonl")
    assert [e["direction"] for e in entries] == ["in", "out"]
    assert entries[0]["text"] == "hello"
    assert entries[0]["user_id"] == 42
    assert entries[0]["chat_id"] == "123"
    assert entries[1]["user_id"] is None  # bot replies have no user id
    assert "ts" in entries[0]


def test_separate_files_per_chat(tmp_path):
    log = TranscriptLog(str(tmp_path))
    log.record("111", "in", "a")
    log.record("222", "in", "b")
    assert (tmp_path / "111.jsonl").exists()
    assert (tmp_path / "222.jsonl").exists()


def test_appends_across_calls(tmp_path):
    log = TranscriptLog(str(tmp_path))
    log.record("c", "in", "one")
    # A fresh logger over the same dir must append, not truncate.
    TranscriptLog(str(tmp_path)).record("c", "out", "two")
    assert len(_read(tmp_path / "c.jsonl")) == 2


def test_unsafe_chat_id_is_sanitised_into_filename(tmp_path):
    log = TranscriptLog(str(tmp_path))
    log.record("../../etc/passwd", "in", "x")
    files = [p.name for p in tmp_path.iterdir()]
    # Separators are stripped (no traversal); the result is a single flat file.
    assert files == [".._.._etc_passwd.jsonl"]
    assert "/" not in files[0]


def test_write_failure_is_swallowed(tmp_path):
    # Point the logger at a path whose parent is a file, so mkdir fails.
    blocker = tmp_path / "afile"
    blocker.write_text("not a dir")
    log = TranscriptLog(str(blocker / "sub"))
    log.record("c", "in", "x")  # must not raise


def test_config_default_enables_logging():
    assert TelegramConfig().history_dir == "logs/telegram"
