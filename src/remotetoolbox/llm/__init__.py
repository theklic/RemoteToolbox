"""LLM backends. Today: Ollama and OpenAI-style servers (e.g. llama.cpp). The :class:`LLMBackend` interface is the
extension point — implement it to add another local (or remote) model server.
"""

from __future__ import annotations

from ..config import LLMConfig
from .base import LLMBackend, LLMMessage, ToolCall

__all__ = ["LLMBackend", "LLMMessage", "ToolCall", "build_backend"]


def build_backend(config: LLMConfig) -> LLMBackend:
    """Factory: turn an ``llm:`` config block into a backend instance."""
    if config.backend == "ollama":
        from .ollama import OllamaBackend

        return OllamaBackend(config.ollama)
    if config.backend == "openai":
        from .openai import OpenAIBackend

        return OpenAIBackend(config.openai)
    raise ValueError(
        f"Unknown llm.backend {config.backend!r}. "
        f"Built-in options: 'ollama', 'openai'. See docs/ARCHITECTURE.md to add one."
    )
