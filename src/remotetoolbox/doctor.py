"""``remotetoolbox doctor`` — a manual preflight check.

Answers "why doesn't it work?" in one command by checking the common
environmental failure points: Ollama reachable + model pulled, Telegram token
and allowlist, tools paths exist, and how many tools were discovered.

This is **opt-in/manual** by design — RemoteToolbox does not run an automatic
preflight at startup.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import Config
from .tooling import load_tools


@dataclass
class Check:
    ok: bool
    label: str
    detail: str = ""


TagsFn = Callable[[str], Awaitable[list[str]]]


async def _http_tags(host: str) -> list[str]:
    async with httpx.AsyncClient(base_url=host.rstrip("/"), timeout=5.0) as client:
        resp = await client.get("/api/tags")
        resp.raise_for_status()
        data = resp.json()
    return [m.get("name", "") for m in data.get("models", [])]


async def gather_checks(config: Config, *, tags_fn: TagsFn = _http_tags) -> list[Check]:
    """Run all checks and return their results (no printing — testable)."""
    checks: list[Check] = []

    if config.llm.backend == "ollama":
        host = config.llm.ollama.host
        model = config.llm.ollama.model
        try:
            tags = await tags_fn(host)
            checks.append(Check(True, f"Ollama reachable at {host}", f"{len(tags)} model(s)"))
            # Accept an exact match or a tag of the same base (e.g. llama3.1:latest).
            present = any(t == model or t.split(":")[0] == model for t in tags)
            checks.append(
                Check(
                    present,
                    f"Model '{model}' available",
                    "" if present else f"not pulled — run: ollama pull {model}",
                )
            )
        except Exception as exc:  # noqa: BLE001 - report any failure as a failed check
            checks.append(
                Check(False, f"Ollama reachable at {host}", f"{exc} — is `ollama serve` running?")
            )
            checks.append(Check(False, f"Model '{model}' available", "skipped (server unreachable)"))

    if config.chat.adapter == "telegram":
        tg = config.chat.telegram
        checks.append(
            Check(
                bool(tg.token),
                "Telegram token set",
                "" if tg.token else "set TELEGRAM_BOT_TOKEN in .env",
            )
        )
        allowed = tg.allowed_user_ids_ordered
        checks.append(
            Check(
                bool(allowed),
                "Telegram allowlist non-empty",
                f"{len(allowed)} user(s)" if allowed else "empty = nobody; set RTB_ALLOWED_USERS",
            )
        )

    for raw in config.tools.paths:
        path = Path(raw).expanduser()
        checks.append(Check(path.exists(), f"Tools path {raw}", "" if path.exists() else "missing"))

    try:
        toolset = await load_tools(config.tools)
        names = toolset.names()
        await toolset.aclose()
        checks.append(Check(True, "Tools discovered", f"{len(names)}: {', '.join(names) or 'none'}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check(False, "Tools discovered", str(exc)))

    return checks


def render(checks: list[Check]) -> int:
    """Print check results; return a process exit code (0 = all OK)."""
    all_ok = True
    for c in checks:
        line = f"  {'✓' if c.ok else '✗'} {c.label}"
        if c.detail:
            line += f" — {c.detail}"
        print(line)
        all_ok = all_ok and c.ok
    print("\nAll checks passed." if all_ok else "\nSome checks failed — see above.")
    return 0 if all_ok else 1
