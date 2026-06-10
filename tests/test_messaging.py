"""Outbound messaging primitive (notify / notify_agent).

We run a real event loop on a background thread (as the adapters do) and check
that notify schedules delivery onto it thread-safely.
"""

from __future__ import annotations

import asyncio
import threading

import pytest

from remotetoolbox import messaging


@pytest.fixture()
def loop_thread():
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=loop.run_forever, daemon=True)
    t.start()
    try:
        yield loop
    finally:
        loop.call_soon_threadsafe(loop.stop)
        t.join(timeout=2)
        messaging.reset()


@pytest.fixture(autouse=True)
def _clean():
    messaging.reset()
    yield
    messaging.reset()


def test_notify_without_messenger_raises():
    with pytest.raises(RuntimeError, match="no active messenger"):
        messaging.notify("hi", to="1")


def test_notify_requires_a_target(loop_thread):
    sent: list[tuple[str, str]] = []

    async def send(text: str, to: str) -> None:
        sent.append((to, text))

    messaging.configure(send=send, loop=loop_thread, default_to=None)
    with pytest.raises(RuntimeError, match="no target chat"):
        messaging.notify("hi")  # no to= and no default


def test_notify_delivers_to_default_and_explicit_target(loop_thread):
    sent: list[tuple[str, str]] = []

    async def send(text: str, to: str) -> None:
        sent.append((to, text))

    messaging.configure(send=send, loop=loop_thread, default_to=999)

    messaging.notify("via default").result(timeout=2)
    messaging.notify("to bob", to="123").result(timeout=2)

    assert ("999", "via default") in sent
    assert ("123", "to bob") in sent


class _RecordingOrchestrator:
    def __init__(self) -> None:
        self.handled: list[str] = []  # chat_ids the agent ran under

    async def handle(self, chat_id: str, prompt: str) -> str:
        self.handled.append(chat_id)
        return f"digest for {chat_id}: {prompt.upper()}"


def test_notify_agent_runs_prompt_then_sends(loop_thread):
    sent: list[tuple[str, str]] = []

    async def send(text: str, to: str) -> None:
        sent.append((to, text))

    orch = _RecordingOrchestrator()
    messaging.configure(send=send, loop=loop_thread, default_to="42", orchestrator=orch)

    messaging.notify_agent("morning digest").result(timeout=2)
    # Delivered to the real chat (42)...
    assert sent == [("42", "digest for 42#proactive: MORNING DIGEST")]
    # ...but the agent ran in a SEPARATE history namespace, not the user's chat.
    assert orch.handled == ["42#proactive"]


def test_notify_agent_does_not_touch_interactive_history(loop_thread):
    async def send(text: str, to: str) -> None: ...

    orch = _RecordingOrchestrator()
    messaging.configure(send=send, loop=loop_thread, default_to="42", orchestrator=orch)

    messaging.notify_agent("digest", to="999").result(timeout=2)
    assert orch.handled == ["999#proactive"]  # never the bare interactive id "999"


def test_notify_agent_share_history_uses_interactive_chat(loop_thread):
    async def send(text: str, to: str) -> None: ...

    orch = _RecordingOrchestrator()
    messaging.configure(send=send, loop=loop_thread, default_to="42", orchestrator=orch)

    messaging.notify_agent("digest", to="999", share_history=True).result(timeout=2)
    assert orch.handled == ["999"]


def test_notify_agent_without_orchestrator_raises(loop_thread):
    async def send(text: str, to: str) -> None: ...

    messaging.configure(send=send, loop=loop_thread, default_to="1")  # no orchestrator
    with pytest.raises(RuntimeError, match="agent isn't available"):
        messaging.notify_agent("x")


def test_delivery_failure_is_swallowed_not_raised(loop_thread, caplog):
    async def send(text: str, to: str) -> None:
        raise RuntimeError("telegram down")

    messaging.configure(send=send, loop=loop_thread, default_to="1")
    fut = messaging.notify("boom")
    with pytest.raises(RuntimeError, match="telegram down"):
        fut.result(timeout=2)  # the caller *can* observe it via the future
    # ...but it was also logged, and never propagated to break the tool.
