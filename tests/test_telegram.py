"""Telegram adapter helpers that don't need the `telegram` extra installed:
message chunking (4096-char limit) and the ordered allowlist accessor.
"""

from __future__ import annotations

from remotetoolbox.chat.telegram import _TELEGRAM_LIMIT, _chunks
from remotetoolbox.config import TelegramConfig


def test_chunks_short_text_is_one_piece():
    assert _chunks("hello") == ["hello"]


def test_chunks_empty_text_yields_nothing():
    # Telegram rejects empty messages, so don't emit one.
    assert _chunks("") == []


def test_chunks_hard_splits_long_text_with_no_newlines():
    text = "x" * (_TELEGRAM_LIMIT * 2 + 100)
    parts = _chunks(text)
    assert all(len(p) <= _TELEGRAM_LIMIT for p in parts)
    assert "".join(parts) == text  # nothing dropped on hard splits
    assert len(parts) == 3


def test_chunks_prefers_newline_boundaries():
    a = "a" * 4000
    b = "b" * 4000
    parts = _chunks(f"{a}\n{b}")  # 8001 chars, one newline in the middle
    assert parts == [a, b]  # split on the newline, which is consumed
    assert all(len(p) <= _TELEGRAM_LIMIT for p in parts)


def test_allowed_user_ids_ordered_follows_config_not_set_order():
    cfg = TelegramConfig(allowed_users="222, 111 , 333")
    assert cfg.allowed_user_ids_ordered == [222, 111, 333]  # config order, for default target
    assert cfg.allowed_user_ids == {111, 222, 333}  # membership unchanged


def test_allowed_user_ids_ordered_dedupes_and_ignores_junk():
    cfg = TelegramConfig(allowed_users="111,111, ,abc,222")
    assert cfg.allowed_user_ids_ordered == [111, 222]
