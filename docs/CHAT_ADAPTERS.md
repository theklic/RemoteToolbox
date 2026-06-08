# Adding a chat adapter

Want Discord, Matrix, Slack, SMS, or a web UI instead of Telegram? Implement one
class. The contract is in [`chat/base.py`](../src/remotetoolbox/chat/base.py).

## The contract

```python
class ChatAdapter(ABC):
    def __init__(self, assemble: Assemble) -> None: ...
    @abstractmethod
    def serve(self) -> None:
        """Build the orchestrator and serve until interrupted. Blocking."""
```

- `serve()` is **synchronous and blocking** — each adapter owns its event-loop
  strategy (see [ARCHITECTURE.md](ARCHITECTURE.md#why-adapters-expose-a-blocking-serve)).
- `self._assemble` is an **async factory** that builds the `Orchestrator`. Call
  it **inside whatever loop your adapter runs**, then stash the result on
  `self.orchestrator`. This keeps the Ollama HTTP client and any MCP sessions on
  the correct loop.
- Per conversation, call `await self.orchestrator.handle(chat_id, text)` and send
  the returned string back to the user. Use a stable `chat_id` per
  conversation/user so histories don't mix.
- Optionally support a reset command via `self.orchestrator.reset(chat_id)`.

## Template

```python
# src/remotetoolbox/chat/discord.py
import asyncio
from .base import ChatAdapter

class DiscordAdapter(ChatAdapter):
    def __init__(self, config, assemble):
        super().__init__(assemble)
        self.config = config

    def serve(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        self.orchestrator = await self._assemble()   # build inside this loop
        try:
            # ... connect to Discord, then per incoming message:
            #     reply = await self.orchestrator.handle(str(channel_id), text)
            #     await send(reply)
            await self._run_client()
        finally:
            await self.orchestrator.aclose()
```

If your chat library insists on running its own loop (like
`python-telegram-bot`'s `run_polling()`), don't wrap it in `asyncio.run`. Build
the orchestrator in the library's startup hook instead — see
[`chat/telegram.py`](../src/remotetoolbox/chat/telegram.py) using `post_init`.

## Register it in the factory

Add one branch to [`chat/__init__.py`](../src/remotetoolbox/chat/__init__.py):

```python
if config.adapter == "discord":
    from .discord import DiscordAdapter
    return DiscordAdapter(config.discord, assemble)
```

…and add a matching `discord:` block to the config model in
[`config.py`](../src/remotetoolbox/config.py) for any settings you need
(token, allowed users, etc.).

## Don't forget access control

Whatever the frontend, **gate who can talk to it** — the agent can call real
tools. Telegram uses an allowlist of user IDs (empty = nobody). Implement the
equivalent for your platform and default to closed. See [SECURITY.md](SECURITY.md).
