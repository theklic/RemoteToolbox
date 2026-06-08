"""The agent loop: chat message -> LLM -> tool calls -> LLM -> reply.

The orchestrator is the heart of RemoteToolbox and is deliberately small. It is
backend- and frontend-agnostic: it speaks :class:`LLMMessage` to the LLM and
:class:`Toolset` to the tools, and exposes one method, :meth:`handle`, that a
chat adapter calls with a user's text.

Conversation history is kept per ``chat_id`` so multiple Telegram users (or
threads) don't bleed into each other.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from .config import AgentConfig, OllamaConfig
from .llm.base import LLMBackend, LLMMessage
from .tooling import Toolset

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        llm: LLMBackend,
        toolset: Toolset,
        agent_config: AgentConfig,
        llm_runtime: OllamaConfig,
    ) -> None:
        self.llm = llm
        self.toolset = toolset
        self.agent = agent_config
        self.max_tool_rounds = llm_runtime.max_tool_rounds
        self._histories: dict[str, list[LLMMessage]] = defaultdict(list)

    def reset(self, chat_id: str) -> None:
        """Forget the conversation for one chat (e.g. a /reset command)."""
        self._histories.pop(chat_id, None)

    async def aclose(self) -> None:
        """Release the LLM and tool resources (HTTP clients, MCP sessions)."""
        await self.llm.aclose()
        await self.toolset.aclose()

    async def handle(self, chat_id: str, user_text: str) -> str:
        """Process one user message and return the agent's text reply."""
        history = self._histories[chat_id]
        history.append(LLMMessage(role="user", content=user_text))

        messages = self._build_messages(history)
        tools = self.toolset.ollama_tools() or None

        for round_num in range(self.max_tool_rounds + 1):
            reply = await self.llm.chat(messages, tools=tools)
            messages.append(reply)
            history.append(reply)

            if not reply.tool_calls:
                self._trim(history)
                return reply.content or "(no response)"

            # The model wants to call tools. Run them, feed results back, loop.
            for call in reply.tool_calls:
                log.info("chat=%s calling tool %s(%s)", chat_id, call.name, call.arguments)
                result = await self.toolset.call(call.name, call.arguments)
                tool_msg = LLMMessage(role="tool", content=result, name=call.name)
                messages.append(tool_msg)
                history.append(tool_msg)

        # Ran out of rounds — ask the model for a final answer without tools.
        log.warning("chat=%s hit max_tool_rounds=%d", chat_id, self.max_tool_rounds)
        final = await self.llm.chat(messages, tools=None)
        history.append(final)
        self._trim(history)
        return final.content or "I wasn't able to finish that in time."

    def _build_messages(self, history: list[LLMMessage]) -> list[LLMMessage]:
        system = LLMMessage(role="system", content=self.agent.system_prompt)
        return [system, *history]

    def _trim(self, history: list[LLMMessage]) -> None:
        """Cap stored history. Trim from the front but never start on a tool
        message (which would dangle without its assistant call)."""
        limit = self.agent.history_limit
        if len(history) <= limit:
            return
        del history[: len(history) - limit]
        while history and history[0].role == "tool":
            del history[0]
