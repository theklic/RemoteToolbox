"""Entry point: ``python -m remotetoolbox`` (or the ``remotetoolbox`` script).

Wires the pieces together and hands control to the configured chat adapter:

    config + .env  ->  Orchestrator(LLM backend, Toolset)  ->  ChatAdapter.serve()
"""

from __future__ import annotations

import argparse
import logging

from .chat import build_adapter
from .config import Config, load_config
from .llm import build_backend
from .orchestrator import Orchestrator
from .tooling import load_tools


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quieten chatty third parties.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def _make_assembler(config: Config):
    """Return an async factory that builds the orchestrator on demand."""

    async def assemble() -> Orchestrator:
        toolset = await load_tools(config.tools)
        llm = build_backend(config.llm)
        return Orchestrator(
            llm=llm,
            toolset=toolset,
            agent_config=config.agent,
            llm_runtime=config.llm.ollama,
        )

    return assemble


def main() -> None:
    parser = argparse.ArgumentParser(prog="remotetoolbox", description=__doc__)
    parser.add_argument("-c", "--config", help="Path to config.yaml", default=None)
    parser.add_argument("--env", help="Path to .env file", default=None)
    args = parser.parse_args()

    config = load_config(args.config, args.env)
    _setup_logging(config.logging.level)
    log = logging.getLogger("remotetoolbox")
    log.info(
        "Starting RemoteToolbox: chat=%s llm=%s/%s",
        config.chat.adapter,
        config.llm.backend,
        config.llm.ollama.model,
    )

    adapter = build_adapter(config.chat, _make_assembler(config))
    adapter.serve()


if __name__ == "__main__":
    main()
