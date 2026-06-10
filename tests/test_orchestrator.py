"""Orchestrator behavior: the agent loop must degrade gracefully instead of
crashing the chat frontend when the LLM backend fails.
"""

from __future__ import annotations

import asyncio
import logging

from remotetoolbox.config import AgentConfig
from remotetoolbox.llm.base import LLMBackend, LLMMessage, ToolCall
from remotetoolbox.orchestrator import Orchestrator
from remotetoolbox.registry import ToolSpec
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
    return Orchestrator(backend, Toolset(), AgentConfig())


def test_backend_error_returned_as_text_not_raised() -> None:
    orch = _orch(_RaisingBackend())
    reply = asyncio.run(orch.handle("c1", "hello"))
    # No exception bubbled up; the user gets the readable message.
    assert reply.startswith("⚠️")
    assert "ollama serve" in reply


def test_normal_reply_still_works() -> None:
    orch = _orch(_PlainBackend())
    assert asyncio.run(orch.handle("c1", "hello")) == "hi there"


class _SlowBackend(LLMBackend):
    """Records enter/exit around a yield point so we can observe interleaving."""

    def __init__(self) -> None:
        self.events: list[str] = []

    async def chat(self, messages, tools=None):
        self.events.append("enter")
        await asyncio.sleep(0.05)
        self.events.append("exit")
        return LLMMessage(role="assistant", content="ok")


def test_same_chat_turns_are_serialized() -> None:
    backend = _SlowBackend()
    orch = _orch(backend)

    async def go():
        await asyncio.gather(orch.handle("c", "a"), orch.handle("c", "b"))

    asyncio.run(go())
    # With the per-chat lock the two turns don't interleave.
    assert backend.events == ["enter", "exit", "enter", "exit"]


def test_different_chats_run_concurrently() -> None:
    backend = _SlowBackend()
    orch = _orch(backend)

    async def go():
        await asyncio.gather(orch.handle("a", "x"), orch.handle("b", "y"))

    asyncio.run(go())
    # Different chats hold different locks, so they overlap.
    assert backend.events == ["enter", "enter", "exit", "exit"]


class _CallThenAnswer(LLMBackend):
    """First call asks to run a tool with a secret arg, then answers."""

    def __init__(self) -> None:
        self.n = 0

    async def chat(self, messages, tools=None):
        self.n += 1
        if self.n == 1:
            return LLMMessage(
                role="assistant",
                tool_calls=[ToolCall(id="1", name="login", arguments={"api_token": "s3cr3t-VALUE"})],
            )
        return LLMMessage(role="assistant", content="done")


def test_tool_argument_values_are_not_logged_at_info(caplog) -> None:
    def login(api_token: str) -> str:
        return "ok"

    spec = ToolSpec(
        name="login",
        description="Log in.",
        parameters={"type": "object", "properties": {"api_token": {"type": "string"}}},
        func=login,
    )
    orch = Orchestrator(_CallThenAnswer(), Toolset(specs={"login": spec}), AgentConfig())

    with caplog.at_level(logging.INFO, logger="remotetoolbox.orchestrator"):
        asyncio.run(orch.handle("c1", "log me in"))

    info = "\n".join(r.getMessage() for r in caplog.records if r.levelno == logging.INFO)
    assert "login" in info and "api_token" in info   # tool + arg name are fine
    assert "s3cr3t-VALUE" not in info                # the secret VALUE must not leak
