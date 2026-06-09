"""Outbound messaging — let a tool push a message to the user, *unprompted*.

RemoteToolbox is normally **reactive**: a chat message comes in, the agent
replies. This module adds the one primitive needed for **proactive** messages —
morning digests, alerts, "backup finished" pings:

    from remotetoolbox import notify, notify_agent

    notify("✅ Nightly backup finished.")              # a message you composed
    notify_agent("Write my morning digest.")           # let the agent compose it

The framework only provides the *send*. **When and why to send — a timer, a
threshold, an external trigger — is entirely up to your tool.** A tool might
start a ``threading.Timer``, watch a sensor, or just send during a normal call.

Notes:
- ``notify`` is **fire-and-forget** and **thread-safe** (safe to call from a
  background thread your tool started). It returns a ``concurrent.futures.Future``
  you can ignore, or ``.result()`` on from a non-event-loop thread if you need to
  wait/confirm.
- Outbound delivery needs RemoteToolbox to be **running with a chat adapter**
  (``python -m remotetoolbox``). The active adapter (Telegram / console) is wired
  in at startup.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from concurrent.futures import Future
from typing import Any

log = logging.getLogger(__name__)

# (text, chat_id) -> awaitable that delivers the message.
SendFn = Callable[[str, str], Awaitable[None]]


class _Messenger:
    send: SendFn | None = None
    loop: asyncio.AbstractEventLoop | None = None
    default_to: str | None = None
    orchestrator: Any = None  # kept loose to avoid an import cycle


_M = _Messenger()


def configure(
    *,
    send: SendFn,
    loop: asyncio.AbstractEventLoop,
    default_to: str | int | None = None,
    orchestrator: Any = None,
) -> None:
    """Wire the active chat adapter's send capability. Called by adapters at startup."""
    _M.send = send
    _M.loop = loop
    _M.default_to = None if default_to is None else str(default_to)
    _M.orchestrator = orchestrator


def reset() -> None:
    """Clear the active messenger (on shutdown / between tests)."""
    _M.send = None
    _M.loop = None
    _M.default_to = None
    _M.orchestrator = None


def is_active() -> bool:
    return _M.send is not None and _M.loop is not None


def _resolve(to: str | int | None) -> str:
    target = to if to is not None else _M.default_to
    if target is None or str(target) == "":
        raise RuntimeError(
            "notify(): no target chat. Pass to=<chat_id>, or rely on the default "
            "(the Telegram adapter defaults to your first allowed user)."
        )
    return str(target)


def _require_active() -> None:
    if not is_active():
        raise RuntimeError(
            "notify(): no active messenger. Outbound messages need RemoteToolbox "
            "running with a chat adapter (e.g. `python -m remotetoolbox`)."
        )


def _schedule(make_coro: Callable[[], Awaitable[None]]) -> Future:
    assert _M.loop is not None
    fut = asyncio.run_coroutine_threadsafe(make_coro(), _M.loop)

    def _log_err(f: Future) -> None:
        exc = f.exception()
        if exc is not None:
            log.error("notify delivery failed: %s", exc)

    fut.add_done_callback(_log_err)
    return fut


def notify(text: str, to: str | int | None = None) -> Future:
    """Send ``text`` to a chat, unprompted.

    text: The message to send.
    to: Chat id to send to. Defaults to the adapter's default chat (for Telegram,
        your first allowed user).

    Returns a Future (fire-and-forget — you can ignore it).
    """
    _require_active()
    target = _resolve(to)
    send = _M.send
    assert send is not None
    return _schedule(lambda: send(text, target))


def notify_agent(prompt: str, to: str | int | None = None) -> Future:
    """Run ``prompt`` through the agent (tools + LLM) and send the reply to a chat.

    Use this for LLM-composed messages — e.g. a morning digest where the agent
    calls your other tools and summarises. ``to`` doubles as the conversation id.
    """
    _require_active()
    if _M.orchestrator is None:
        raise RuntimeError("notify_agent(): the agent isn't available in this context.")
    target = _resolve(to)
    orchestrator = _M.orchestrator
    send = _M.send
    assert send is not None

    async def _run() -> None:
        reply = await orchestrator.handle(target, prompt)
        await send(reply, target)

    return _schedule(_run)
