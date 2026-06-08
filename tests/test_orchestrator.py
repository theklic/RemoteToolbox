"""Orchestrator behavior: the agent loop must degrade gracefully instead of
crashing the chat frontend when the LLM backend fails.
"""

from __future__ import annotations

import asyncio

from remotetoolbox.config import AgentConfig, OllamaConfig
from remotetoolbox.llm.base import LLMBackend, LLMMessage
from remotetoolbox.orchestrator import Orchestrator
from remotetoolbox.tooling import Toolset


class _RaisingBackend(LLMBackend):
    async def chat(self, messages, tools=None):
        raise RuntimeError(
            "Could not reach Ollama at http://localhost:11434: nope. "
            "Is `ollama serve` running and the model pulled?"
        )


class _PlainBackend(LLMBackend):
    async def chat(self, messages, tools=None):
        return LLMMessage(role="assistant", content="hi there")


def _orch(backend: LLMBackend) -> Orchestrator:
    return Orchestrator(backend, Toolset(), AgentConfig(), OllamaConfig())


def test_backend_error_returned_as_text_not_raised() -> None:
    orch = _orch(_RaisingBackend())
    reply = asyncio.run(orch.handle("c1", "hello"))
    # No exception bubbled up; the user gets the readable message.
    assert reply.startswith("⚠️")
    assert "ollama serve" in reply


def test_normal_reply_still_works() -> None:
    orch = _orch(_PlainBackend())
    assert asyncio.run(orch.handle("c1", "hello")) == "hi there"
