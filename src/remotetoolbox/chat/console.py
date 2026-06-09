"""Console adapter — chat with the agent in your terminal.

Zero external dependencies and no tokens required, so it's the default and the
best way to verify your tools work before exposing anything remotely.

Commands: ``/reset`` clears the conversation, ``/quit`` exits.
"""

from __future__ import annotations

import asyncio

from .. import messaging
from .base import ChatAdapter

_CHAT_ID = "console"


class ConsoleAdapter(ChatAdapter):
    def serve(self) -> None:
        try:
            asyncio.run(self._serve())
        except KeyboardInterrupt:
            print()

    async def _send(self, text: str, to: str) -> None:
        # Proactive/outbound message (e.g. from a tool's notify()).
        print(f"\n[outbound → {to}] {text}\n")

    async def _serve(self) -> None:
        self.orchestrator = await self._assemble()
        loop = asyncio.get_running_loop()
        messaging.configure(
            send=self._send, loop=loop, default_to=_CHAT_ID, orchestrator=self.orchestrator
        )
        print("RemoteToolbox console. Type a message, /reset to clear, /quit to exit.\n")
        try:
            while True:
                try:
                    user_text = await loop.run_in_executor(None, input, "you › ")
                except (EOFError, KeyboardInterrupt):
                    print()
                    return

                text = user_text.strip()
                if not text:
                    continue
                if text in ("/quit", "/exit"):
                    return
                if text == "/reset":
                    self.orchestrator.reset(_CHAT_ID)
                    print("bot › (conversation cleared)\n")
                    continue

                reply = await self.orchestrator.handle(_CHAT_ID, text)
                print(f"bot › {reply}\n")
        finally:
            messaging.reset()
            await self.orchestrator.aclose()
