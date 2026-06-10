# BACKLOG — prioritized work items

This is the actionable backlog from a full project review (post-PR #5). Items are
written so a coding agent can pick one up and work it through end-to-end without
extra context. Work top-down within a priority band unless told otherwise.

## How to work an item (read first)

- Read [`CLAUDE.md`](CLAUDE.md) for conventions. Run `pytest` and `ruff check src tests`
  before pushing; CI runs both plus the docs-sync guards.
- If you touch `config.py`, a contract, or an error message, update
  [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) / [`docs/REFERENCE.md`](docs/REFERENCE.md)
  **in the same commit** — `tests/test_docs_sync.py` enforces this.
- Add or extend a test for every behavior change. Mark an item done by deleting it
  from this file in the same PR that fixes it.

**Decisions already made by the project owner — do not re-open:**

- No built-in scheduler. Tools own when/why to send proactive messages.
- No *automatic* startup preflight warning (declined). The *manual* `remotetoolbox
  doctor` command is the accepted form (shipped).
- Example tools must never schedule themselves; self-scheduling patterns stay
  commented out.
- `extra="forbid"` config strictness and `agent.max_tool_rounds` placement are
  settled.

---

## P3 — opportunities (each is its own conversation; confirm scope before building)

- **P3-1 Packaging/PyPI:** `scaffold.py` resolves its template via
  `parents[2]/examples`, which only exists in a git checkout — `pip install
  remotetoolbox` from PyPI can't ship `init-tools` today. Move templates into
  package data (`src/remotetoolbox/templates/…`), keep `examples/tools-repo` as
  a thin pointer, tag `v0.1.0`, add a framework `CHANGELOG.md`.
- **P3-2 Second chat adapter:** Discord or Matrix, via the documented
  `ChatAdapter` contract (`docs/CHAT_ADAPTERS.md`). Must implement allowlist
  access control and wire `messaging.configure` like the Telegram adapter.
- **P3-3 Streaming replies:** Ollama supports streaming; long generations
  currently look frozen. Console could print incrementally; Telegram could edit
  a placeholder message. Touches the `LLMBackend` contract — design first.
- **P3-4 Opt-in history persistence:** swap `Orchestrator._histories` behind a
  tiny store interface with an sqlite implementation; off by default
  (`agent.persist_history`). Restart currently forgets conversations (documented
  behavior).
- **P3-5 Ship a `Dockerfile`:** currently only documented inline in
  `docs/DEPLOYMENT.md`. Ship the file + a compose example mounting the
  gitignored `tools/`, `.env`, `config.yaml`.
- **P3-6 Notify quiet hours / rate limit:** config-level guard (e.g.
  `messaging.quiet_hours`, `messaging.max_per_hour`) so a buggy tool can't spam
  3am pings. Keep default permissive; this is a safety valve, not a scheduler.
- **P3-7 Community scaffolding:** `CONTRIBUTING.md`, issue/PR templates, GitHub
  topics + repo description for discoverability.

---

## Accepted / documented — do NOT "fix" these

- Sequential update processing (one turn at a time) — fine for the single-tenant
  design. Revisit only with a real multi-user need (then: PTB
  `concurrent_updates=True`; the per-chat locks in `orchestrator.py` already
  keep same-chat turns from interleaving).
- `⚠️ {exc}` error replies may include host URLs — accepted; documented in
  `docs/SECURITY.md`.
- Proactive-notify spam risk from a hostile/buggy tool — documented in
  `docs/SECURITY.md` (P3-6 is the optional mitigation).
- In-memory history loss on restart — documented in `docs/ARCHITECTURE.md`
  (P3-4 is the optional change).
