"""Proactive (outbound) messages — the framework sends; your tool decides when.

Copy to try:  cp -r examples/tools/proactive tools/proactive

`notify()` pushes a message to your chat unprompted. `notify_agent()` has the
agent (tools + LLM) compose the message first — handy for digests.
"""

from __future__ import annotations

from remotetoolbox import notify, notify_agent, tool


@tool(description="Send myself a reminder message right now.")
def remind_me(text: str) -> str:
    """Push a reminder to the chat.

    text: What to be reminded about.
    """
    notify(f"⏰ Reminder: {text}")
    return "Reminder sent."


@tool(description="Generate and push a morning digest via the agent.")
def send_morning_digest() -> str:
    """Ask the agent to write a digest (it can call your other tools + the LLM)
    and deliver it. WHEN to call this is up to you — e.g. a cron job that runs a
    prompt, or the scheduler pattern below."""
    notify_agent(
        "Write a short, friendly morning digest. Use any tools you have "
        "(weather, calendar, todos) and keep it to a few lines."
    )
    return "Digest requested; it will arrive shortly."


# --- Pattern: a tool that schedules ITSELF (the tool owns the 'when') ---------
#
# RemoteToolbox has no built-in scheduler — timing is your tool's job. One way is
# a background timer started when this module loads. Uncomment to use, and set
# your own time logic:
#
#   import threading, datetime
#
#   def _send_digest() -> None:
#       notify_agent("Write my morning digest.")
#       _schedule_next()
#
#   def _schedule_next() -> None:
#       now = datetime.datetime.now()
#       nxt = now.replace(hour=7, minute=0, second=0, microsecond=0)
#       if nxt <= now:
#           nxt += datetime.timedelta(days=1)
#       threading.Timer((nxt - now).total_seconds(), _send_digest).start()
#
#   _schedule_next()   # runs at import (startup)
#
# (notify/notify_agent are thread-safe, so calling them from the Timer thread is
# fine. Outbound delivery only works while RemoteToolbox is running.)
