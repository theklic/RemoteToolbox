"""The LLM backend contract and the normalized message types the orchestrator
speaks. Backends translate between these and their wire format.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A request from the model to invoke one tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMMessage:
    """A single normalized chat message.

    ``role`` is one of: ``system``, ``user``, ``assistant``, ``tool``.
    Assistant messages may carry ``tool_calls``; tool messages carry the result
    of a call plus the ``name`` of the tool that produced it.
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    name: str | None = None  # tool name, for role == "tool"


class LLMBackend(ABC):
    """Implement this to plug in a model server.

    The orchestrator only needs one method: given the conversation so far and
    the available tools, return the assistant's next message (which may contain
    tool calls).
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMMessage:
        """Return the assistant's reply. ``tools`` are OpenAI/Ollama-format specs."""

    async def aclose(self) -> None:
        """Release resources (network clients, etc.). Override if needed."""
        return None
