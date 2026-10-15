"""OpenAI-style backend — any server with ``/v1/chat/completions`` and tool
calling, such as llama.cpp's ``llama-server``.

Differences from the Ollama wire format that matter here: tool-call arguments
travel as a JSON *string*, and each tool result names the call it answers with
``tool_call_id``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

import httpx

from ..config import OpenAIConfig
from .base import LLMBackend, LLMMessage, ToolCall

log = logging.getLogger(__name__)


class OpenAIBackend(LLMBackend):
    def __init__(self, config: OpenAIConfig) -> None:
        self.config = config
        self._client = httpx.AsyncClient(
            base_url=config.host.rstrip("/"),
            timeout=httpx.Timeout(config.request_timeout, connect=10.0),
        )

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMMessage:
        payload: dict[str, Any] = {
            **self.config.options,
            "messages": [self._to_wire(m) for m in messages],
            "stream": False,
        }
        if self.config.model:
            payload["model"] = self.config.model
        if tools:
            payload["tools"] = [{"type": "function", **t} if "type" not in t else t for t in tools]

        # A shared server may be restarting (connection refused) or loading its model (503).
        # Keep retrying for up to wait_for_server seconds; other errors fail at once.
        deadline = time.monotonic() + self.config.wait_for_server
        while True:
            try:
                resp = await self._client.post("/v1/chat/completions", json=payload)
                if resp.status_code == 503 and time.monotonic() < deadline:
                    log.warning("model server loading (503), waiting…")
                    await asyncio.sleep(3)
                    continue
                resp.raise_for_status()
                choice = (resp.json().get("choices") or [{}])[0]
                return self._from_wire(choice.get("message") or {})
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Model server returned {exc.response.status_code}: {exc.response.text[:300]}"
                ) from exc
            except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                if time.monotonic() < deadline:
                    log.warning("model server unreachable (%s), waiting…", type(exc).__name__)
                    await asyncio.sleep(3)
                    continue
                raise RuntimeError(f"Could not reach the model server at {self.config.host}: {exc}") from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Could not reach the model server at {self.config.host}: {exc}") from exc

    # --- translation ---------------------------------------------------------

    @staticmethod
    def _to_wire(msg: LLMMessage) -> dict[str, Any]:
        wire: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.role == "tool":
            if msg.tool_call_id:
                wire["tool_call_id"] = msg.tool_call_id
            if msg.name:
                wire["name"] = msg.name
        if msg.tool_calls:
            wire["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in msg.tool_calls
            ]
        return wire

    @staticmethod
    def _from_wire(message: dict[str, Any]) -> LLMMessage:
        tool_calls: list[ToolCall] = []
        for raw in message.get("tool_calls") or []:
            fn = raw.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append(
                ToolCall(id=raw.get("id") or uuid.uuid4().hex, name=fn.get("name", ""), arguments=args or {})
            )
        return LLMMessage(
            role=message.get("role", "assistant"),
            content=message.get("content", "") or "",
            tool_calls=tool_calls,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
