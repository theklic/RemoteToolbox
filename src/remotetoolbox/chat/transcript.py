"""Append-only chat-transcript logging for chat adapters.

A :class:`TranscriptLog` records each turn of a conversation (inbound user
messages and outbound bot replies) to a JSONL file — one file per ``chat_id`` —
under a configured directory. This lets a remote operator review what was said
after the fact, which the in-memory ``agent.history_limit`` window can't.

Transcripts can contain private content, so the directory is meant to live under
a **gitignored** path (the shipped default, ``logs/``, is already ignored). They
must never be committed. See docs/CONFIGURATION.md.

Logging must never break a conversation: write failures are logged once and then
swallowed, so a full disk or a bad path degrades to "no transcript", not a crash.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

# A chat_id becomes a filename, so restrict it to a safe charset.
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


class TranscriptLog:
    """Append chat turns to per-chat JSONL files.

    A blank ``directory`` produces a disabled (no-op) logger, so callers can wire
    it unconditionally and let configuration decide whether anything is written.
    """

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory).expanduser() if directory.strip() else None
        self._warned = False

    @property
    def enabled(self) -> bool:
        return self.directory is not None

    def _path_for(self, chat_id: str) -> Path:
        assert self.directory is not None
        safe = _UNSAFE.sub("_", chat_id) or "unknown"
        return self.directory / f"{safe}.jsonl"

    def record(
        self,
        chat_id: str,
        direction: str,
        text: str,
        *,
        user_id: int | None = None,
    ) -> None:
        """Append one turn to the chat's transcript.

        chat_id: the conversation this turn belongs to (used as the filename).
        direction: ``"in"`` (from the user) or ``"out"`` (from the bot).
        text: the message content.
        user_id: the sender's numeric id for inbound turns; ``None`` for the bot.
        """
        if self.directory is None:
            return
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "chat_id": chat_id,
            "user_id": user_id,
            "direction": direction,
            "text": text,
        }
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with self._path_for(chat_id).open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError as exc:
            # Warn once, then stay quiet so a bad path doesn't flood the logs.
            if not self._warned:
                log.warning(
                    "chat transcript logging disabled: cannot write to %s: %s",
                    self.directory,
                    exc,
                )
                self._warned = True
