"""Entry point: ``python -m remotetoolbox`` (or the ``remotetoolbox`` script).

Wires the pieces together and hands control to the configured chat adapter:

    config + .env  ->  Orchestrator(LLM backend, Toolset)  ->  ChatAdapter.serve()
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

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
        return Orchestrator(llm=llm, toolset=toolset, agent_config=config.agent)

    return assemble


def _cmd_init_tools(path: str, no_git: bool) -> None:
    from .scaffold import init_tools

    try:
        dest = init_tools(path, do_git=not no_git)
    except (FileExistsError, FileNotFoundError) as exc:
        raise SystemExit(f"init-tools: {exc}")

    print("\nNext steps:")
    print(f"  1. Add tools under {dest}/  (see docs/WRITING_TOOLS.md)")
    print("  2. Point RemoteToolbox at it in config.yaml:")
    print("       tools:")
    print("         paths:")
    print(f"           - {path}")
    print("  3. Restart RemoteToolbox.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="remotetoolbox", description=__doc__)
    parser.add_argument("-c", "--config", help="Path to config.yaml", default=None)
    parser.add_argument("--env", help="Path to .env file", default=None)

    sub = parser.add_subparsers(dest="command")
    p_init = sub.add_parser(
        "init-tools",
        help="Scaffold a personal tools repo (version history + changelog).",
    )
    p_init.add_argument("path", help="Where to create the tools repo, e.g. ~/rtb-tools")
    p_init.add_argument(
        "--no-git", action="store_true", help="Copy files only; don't run git init/commit."
    )

    sub.add_parser("doctor", help="Check your setup (Ollama, token, tools) and report problems.")

    args = parser.parse_args()

    if args.command == "init-tools":
        _cmd_init_tools(args.path, args.no_git)
        return

    if args.command == "doctor":
        import asyncio

        from .doctor import gather_checks, render

        config = load_config(args.config, args.env)
        raise SystemExit(render(asyncio.run(gather_checks(config))))

    # Default (no subcommand): run the chat agent.
    config = load_config(args.config, args.env)
    _setup_logging(config.logging.level)
    log = logging.getLogger("remotetoolbox")
    log.info(
        "Starting RemoteToolbox: chat=%s llm=%s/%s",
        config.chat.adapter,
        config.llm.backend,
        config.llm.ollama.model,
    )

    _nudge_tools_versioning(config, log)

    adapter = build_adapter(config.chat, _make_assembler(config))
    adapter.serve()


def _nudge_tools_versioning(config: Config, log: logging.Logger) -> None:
    """One-time INFO nudge: if the user keeps tools in the default ./tools and it
    isn't its own git repo, suggest versioning them. Fires only when ./tools is
    actually in use (has tool files) — never for a custom tools.paths."""
    if config.tools.paths != ["./tools"]:
        return  # they've already pointed at a separate location
    tools_dir = Path("./tools")
    if (tools_dir / ".git").exists():
        return  # already its own repo
    has_tools = any(
        not f.name.startswith("_") and "__pycache__" not in f.parts
        for f in tools_dir.glob("*/*.py")
    )
    if not has_tools:
        return
    log.info(
        "Tip: your tools in ./tools aren't versioned. Give them history + rollback "
        "with `python -m remotetoolbox init-tools ~/rtb-tools` (see docs/MANAGING_TOOLS.md)."
    )


if __name__ == "__main__":
    main()
