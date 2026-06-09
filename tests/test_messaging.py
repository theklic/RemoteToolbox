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


def test_notify_agent_runs_prompt_then_sends(loop_thread):
    sent: list[tuple[str, str]] = []

    async def send(text: str, to: str) -> None:
        sent.append((to, text))

    class FakeOrchestrator:
        async def handle(self, chat_id: str, prompt: str) -> str:
            return f"digest for {chat_id}: {prompt.upper()}"

    messaging.configure(send=send, loop=loop_thread, default_to="42", orchestrator=FakeOrchestrator())

    messaging.notify_agent("morning digest").result(timeout=2)
    assert sent == [("42", "digest for 42: MORNING DIGEST")]


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
