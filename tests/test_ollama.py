"""Ollama backend: one cheap retry on transient connection errors."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from remotetoolbox.config import OllamaConfig
from remotetoolbox.llm.base import LLMMessage
from remotetoolbox.llm.ollama import OllamaBackend


class _FakeResp:
    def raise_for_status(self) -> None: ...

    def json(self) -> dict:
        return {"message": {"role": "assistant", "content": "hi"}}


class _FlakyClient:
    """Fails the first POST with a ConnectError, then succeeds."""

    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self._fail_times = fail_times

    async def post(self, url: str, json: dict) -> _FakeResp:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise httpx.ConnectError("connection refused")
        return _FakeResp()

    async def aclose(self) -> None: ...


def test_retries_once_then_succeeds() -> None:
    backend = OllamaBackend(OllamaConfig())
    backend._client = _FlakyClient(fail_times=1)  # type: ignore[assignment]
    reply = asyncio.run(backend.chat([LLMMessage(role="user", content="hi")]))
    assert reply.content == "hi"
    assert backend._client.calls == 2  # initial + one retry


def test_gives_up_after_one_retry() -> None:
    backend = OllamaBackend(OllamaConfig())
    backend._client = _FlakyClient(fail_times=2)  # type: ignore[assignment]
    with pytest.raises(RuntimeError, match="Could not reach Ollama"):
        asyncio.run(backend.chat([LLMMessage(role="user", content="hi")]))
    assert backend._client.calls == 2  # didn't loop forever
