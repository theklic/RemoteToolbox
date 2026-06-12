"""Ollama backend — talks to a local Ollama server's ``/api/chat`` endpoint.

Ollama exposes tool calling in the OpenAI style: you pass ``tools`` and it may
return ``message.tool_calls``. We translate to/from our normalized
:class:`LLMMessage` so the orchestrator stays backend-agnostic.

Docs: https://github.com/ollama/ollama/blob/main/docs/api.md
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx

from ..config import OllamaConfig
from .base import LLMBackend, LLMMessage, ToolCall

log = logging.getLogger(__name__)


class OllamaBackend(LLMBackend):
    def __init__(self, config: OllamaConfig) -> None:
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
            "model": self.config.model,
            "messages": [self._to_wire(m) for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
        if self.config.options:
            payload["options"] = self.config.options

        # One cheap retry on transient connection blips (not on HTTP-status errors).
        attempts = 2
        for attempt in range(attempts):
            try:
                resp = await self._client.post("/api/chat", json=payload)
                resp.raise_for_status()
                return self._from_wire(resp.json().get("message", {}))
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Ollama returned {exc.response.status_code}: {exc.response.text[:300]}"
                ) from exc
            except (httpx.ConnectError, httpx.ReadTimeout) as exc:
                if attempt + 1 < attempts:
                    log.warning(
                        "Ollama %s (attempt %d/%d), retrying…",
                        type(exc).__name__, attempt + 1, attempts,
                    )
                    continue
                raise RuntimeError(
                    f"Could not reach Ollama at {self.config.host}: {exc}. "
                    f"Is `ollama serve` running and the model pulled?"
                ) from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(
                    f"Could not reach Ollama at {self.config.host}: {exc}. "
                    f"Is `ollama serve` running and the model pulled?"
                ) from exc
        raise AssertionError("unreachable")  # pragma: no cover

    # --- translation ---------------------------------------------------------

    @staticmethod
    def _to_wire(msg: LLMMessage) -> dict[str, Any]:
        wire: dict[str, Any] = {"role": msg.role, "content": msg.content}
        if msg.role == "tool" and msg.name:
            wire["tool_name"] = msg.name
        if msg.tool_calls:
            wire["tool_calls"] = [
                {
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
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
            # Ollama usually returns a dict; some models return a JSON string.
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            tool_calls.append(
                ToolCall(id=uuid.uuid4().hex, name=fn.get("name", ""), arguments=args or {})
            )
        return LLMMessage(
            role=message.get("role", "assistant"),
            content=message.get("content", "") or "",
            tool_calls=tool_calls,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
