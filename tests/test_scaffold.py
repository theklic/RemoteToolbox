"""Tests for `remotetoolbox init-tools` scaffolding."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from remotetoolbox.scaffold import TEMPLATE_DIR, init_tools


def test_template_exists_and_has_expected_files() -> None:
    # The command copies this directory; make sure it stays intact.
    for rel in (".gitignore", "CHANGELOG.md", "README.md", "hello/tool.py"):
        assert (TEMPLATE_DIR / rel).exists(), f"template missing {rel}"


def test_init_tools_copies_template(tmp_path: Path) -> None:
    dest = tmp_path / "rtb-tools"
    out = init_tools(dest, do_git=False)

    assert out == dest.resolve()
    for rel in (".gitignore", "CHANGELOG.md", "README.md", "hello/tool.py"):
        assert (dest / rel).exists(), f"scaffold missing {rel}"
    # No build cruft copied over.
    assert not list(dest.rglob("__pycache__"))


def test_init_tools_refuses_nonempty_dir(tmp_path: Path) -> None:
    dest = tmp_path / "busy"
    dest.mkdir()
    (dest / "something.txt").write_text("hi")
    with pytest.raises(FileExistsError):
        init_tools(dest, do_git=False)


def test_init_tools_into_empty_existing_dir_is_ok(tmp_path: Path) -> None:
    dest = tmp_path / "empty"
    dest.mkdir()
    init_tools(dest, do_git=False)
    assert (dest / "CHANGELOG.md").exists()


@pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")
def test_init_tools_initializes_git_repo_on_main(tmp_path: Path) -> None:
    import subprocess

    dest = tmp_path / "with-git"
    init_tools(dest, do_git=True)
    # The repo is initialized even if the commit can't be made (no git identity).
    assert (dest / ".git").is_dir()
    # It must be on `main` — the docs (MANAGING_TOOLS.md) assume that branch.
    head = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=dest,
        capture_output=True,
        text=True,
    )
    assert head.stdout.strip() == "main"
