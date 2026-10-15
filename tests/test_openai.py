"""OpenAI-style backend: wire translation and waiting for a shared server."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from remotetoolbox.config import OpenAIConfig
from remotetoolbox.llm.base import LLMMessage, ToolCall
from remotetoolbox.llm.openai import OpenAIBackend


class _Resp:
    def __init__(self, status: int, body: dict | None = None) -> None:
        self.status_code = status
        self._body = body or {}
        self.text = json.dumps(self._body)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._body


OK = {"choices": [{"message": {"role": "assistant", "content": "hi"}}]}


class _Client:
    def __init__(self, script: list) -> None:
        self.script, self.sent = list(script), []

    async def post(self, url: str, json: dict) -> _Resp:
        self.sent.append(json)
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step

    async def aclose(self) -> None: ...


def _backend(script: list, wait: float = 60.0) -> OpenAIBackend:
    b = OpenAIBackend(OpenAIConfig(model="m", wait_for_server=wait, options={"temperature": 0.2}))
    b._client = _Client(script)  # type: ignore[assignment]
    return b


def test_tool_call_round_trip() -> None:
    reply = OpenAIBackend._from_wire({"role": "assistant", "content": "", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "emby_now_playing", "arguments": "{\"x\": 1}"}}]})
    assert reply.tool_calls == [ToolCall(id="c1", name="emby_now_playing", arguments={"x": 1})]
    wire = OpenAIBackend._to_wire(reply)
    assert wire["tool_calls"][0]["function"]["arguments"] == "{\"x\": 1}"
    result = OpenAIBackend._to_wire(LLMMessage(role="tool", content="ok", name="emby_now_playing", tool_call_id="c1"))
    assert result["tool_call_id"] == "c1"


def test_payload_carries_model_options_and_typed_tools() -> None:
    b = _backend([_Resp(200, OK)])
    asyncio.run(b.chat([LLMMessage(role="user", content="hi")], tools=[{"function": {"name": "t"}}]))
    sent = b._client.sent[0]
    assert sent["model"] == "m" and sent["temperature"] == 0.2
    assert sent["tools"][0]["type"] == "function"


def test_waits_through_loading_and_restart() -> None:
    b = _backend([_Resp(503), httpx.ConnectError("refused"), _Resp(200, OK)])
    b_sleep = asyncio.sleep
    async def fast(_s: float) -> None:
        await b_sleep(0)
    import remotetoolbox.llm.openai as mod
    mod.asyncio.sleep = fast  # type: ignore[assignment]
    try:
        assert asyncio.run(b.chat([LLMMessage(role="user", content="hi")])).content == "hi"
    finally:
        mod.asyncio.sleep = b_sleep  # type: ignore[assignment]


def test_gives_up_when_server_stays_down() -> None:
    b = _backend([httpx.ConnectError("refused")], wait=0)
    with pytest.raises(RuntimeError, match="Could not reach the model server"):
        asyncio.run(b.chat([LLMMessage(role="user", content="hi")]))
