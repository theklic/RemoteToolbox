"""The chat adapter contract.

Each adapter owns its own event-loop strategy (the console runs a simple
``asyncio`` loop; Telegram's library insists on running its own), so the public
method is a *blocking* :meth:`serve`. Adapters receive an async ``assemble``
factory that builds the orchestrator inside whatever loop the adapter ends up
running, which keeps loop-bound resources (HTTP clients, MCP sessions) on the
right loop.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from ..orchestrator import Orchestrator

Assemble = Callable[[], Awaitable[Orchestrator]]


class ChatAdapter(ABC):
    def __init__(self, assemble: Assemble) -> None:
        self._assemble = assemble
        self.orchestrator: Orchestrator | None = None

    @abstractmethod
    def serve(self) -> None:
        """Build the orchestrator and serve until interrupted. Blocking."""
