#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# Two jobs, both fixing friction unique to the ephemeral remote container:
#   1. Re-sync the working tree to the live branch tip. Fresh web containers can
#      boot at a stale checkpoint; this fast-forwards to origin so a session
#      never starts on old code. SAFE: only when the tree is clean AND strictly
#      behind upstream (never clobbers uncommitted work or a diverged branch).
#   2. Install dev dependencies so pytest / ruff / mypy work immediately.
#
# Web-only: a local contributor manages their own git and environment.
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0

# 1) Sync to origin tip (clean + fast-forward only) ----------------------------
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo HEAD)"
if [ "$branch" != "HEAD" ]; then
  git fetch origin --quiet "$branch" 2>/dev/null || git fetch origin --quiet 2>/dev/null || true
  upstream="origin/$branch"
  if git rev-parse --verify --quiet "$upstream" >/dev/null; then
    if [ "$(git rev-parse HEAD)" != "$(git rev-parse "$upstream")" ]; then
      if [ -z "$(git status --porcelain)" ] && git merge-base --is-ancestor HEAD "$upstream"; then
        git reset --hard --quiet "$upstream" \
          && echo "session-start: synced to $upstream ($(git rev-parse --short HEAD))"
      else
        echo "session-start: $branch not fast-forwardable to $upstream (dirty or diverged) — left as-is"
      fi
    fi
  fi
fi

# 2) Install dev dependencies (container caches this after the first run) -------
if command -v python >/dev/null 2>&1; then
  if python -m pip install -q -e ".[dev]" >/tmp/rtb-session-deps.log 2>&1; then
    echo "session-start: dev dependencies ready (ruff / mypy / pytest)"
  else
    echo "session-start: dependency install failed — see /tmp/rtb-session-deps.log"
  fi
fi
