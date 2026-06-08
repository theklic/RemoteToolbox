"""Chat adapters: the frontends users talk to.

A :class:`ChatAdapter` connects a chat surface (terminal, Telegram, …) to an
:class:`~remotetoolbox.orchestrator.Orchestrator`. Adding a new frontend means
implementing one class — see docs/CHAT_ADAPTERS.md.
"""

from __future__ import annotations

from ..config import ChatConfig
from .base import Assemble, ChatAdapter

__all__ = ["ChatAdapter", "Assemble", "build_adapter"]


def build_adapter(config: ChatConfig, assemble: Assemble) -> ChatAdapter:
    """Factory: turn a ``chat:`` config block into a servable adapter.

    ``assemble`` is an async factory that builds the orchestrator; the adapter
    calls it inside whatever event loop it runs, so loop-bound resources stay put.
    """
    if config.adapter == "console":
        from .console import ConsoleAdapter

        return ConsoleAdapter(assemble)
    if config.adapter == "telegram":
        from .telegram import TelegramAdapter

        return TelegramAdapter(config.telegram, assemble)
    raise ValueError(
        f"Unknown chat.adapter {config.adapter!r}. "
        f"Built-in options: 'console', 'telegram'. See docs/CHAT_ADAPTERS.md."
    )
