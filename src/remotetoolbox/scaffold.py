"""Scaffold a personal tools repo from the bundled template.

Powers ``python -m remotetoolbox init-tools <path>``. Kept separate from the CLI
so it's easy to test. Copies ``examples/tools-repo`` to the destination and,
unless asked not to, initializes a git repo with a first commit — giving the
user version history and a changelog for their tools, separate from this repo.
See docs/MANAGING_TOOLS.md.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable

# examples/tools-repo lives at the repo root (this file is src/remotetoolbox/scaffold.py).
TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "examples" / "tools-repo"

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git")


def init_tools(
    dest: str | Path,
    *,
    do_git: bool = True,
    log: Callable[[str], None] = print,
) -> Path:
    """Create a tools repo at ``dest`` from the template. Returns the resolved path.

    Raises FileNotFoundError if the template is missing (e.g. installed as a wheel
    without the examples), or FileExistsError if ``dest`` exists and isn't empty.
    """
    target = Path(dest).expanduser().resolve()

    if not TEMPLATE_DIR.exists():
        raise FileNotFoundError(
            f"Template not found at {TEMPLATE_DIR}. Run init-tools from a "
            f"RemoteToolbox checkout, or copy examples/tools-repo manually."
        )
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(
            f"{target} already exists and is not empty. Pick a new or empty path."
        )

    shutil.copytree(TEMPLATE_DIR, target, ignore=_IGNORE, dirs_exist_ok=True)
    log(f"Created tools repo at {target}")

    if do_git:
        if shutil.which("git"):
            _git_init(target, log)
        else:
            log("git not found on PATH — skipped repo init (files are in place).")

    return target


def _git_init(target: Path, log: Callable[[str], None]) -> None:
    if (target / ".git").exists():
        log("Already a git repo — skipped git init.")
        return

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=target, capture_output=True, text=True, check=False
        )

    run("init")
    run("add", "-A")
    commit = run("commit", "-m", "My tools: initial commit")
    if commit.returncode == 0:
        log("Initialized git repo with an initial commit.")
        return

    # Don't fail the scaffold — the files are in place and the repo is staged.
    # Surface git's actual reason (identity, commit signing, a hook, …).
    detail = (commit.stderr or commit.stdout or "").strip()
    reason = f"\n  git said: {detail.splitlines()[-1]}" if detail else ""
    log(
        "Initialized git repo and staged your files, but the first commit didn't "
        f"complete.{reason}\n  Finish it yourself with: cd {target} && git commit -m 'initial'"
    )
