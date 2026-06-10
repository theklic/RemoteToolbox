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
- No *automatic* startup preflight warning (declined). A *manual* `doctor`
  command is acceptable (see P2-1).
- Example tools must never schedule themselves; self-scheduling patterns stay
  commented out.
- `extra="forbid"` config strictness and `agent.max_tool_rounds` placement are
  settled.

---

## P0 — fix before the next release (bugs on the shipped proactive path)

### P0-1: Telegram messages over 4,096 chars fail silently

- **Type:** bug
- **Where:** `src/remotetoolbox/chat/telegram.py` — `on_message`'s
  `update.message.reply_text(reply)` and the outbound `_send` in `_post_init`.
- **Problem:** Telegram rejects messages longer than 4,096 characters. A long
  LLM reply — and especially a `notify_agent` digest — raises `BadRequest`
  inside the handler; python-telegram-bot logs it and the user receives
  *nothing*. No chunking exists (verified: no length handling in the adapter).
- **Approach:** add a small `_chunk(text, limit=4096)` helper (split on
  paragraph/newline boundaries where possible, hard-split otherwise) and use it
  in **both** the reply path and the outbound `_send`. Keep it in the Telegram
  adapter — other adapters don't share the limit.
- **Acceptance:** unit test that a >4,096-char string is split into <=4,096-char
  parts, order preserved, nothing dropped; both send paths use the helper.
  Document the behavior in `docs/REFERENCE.md` (chat adapter contract notes).

### P0-2: `notify_agent` pollutes the user's interactive conversation history

- **Type:** bug (surprising behavior)
- **Where:** `src/remotetoolbox/messaging.py` — `notify_agent` calls
  `orchestrator.handle(target, prompt)` with the *user's own chat id* as the
  conversation id.
- **Problem:** every scheduled digest injects its prompt + reply into the user's
  real DM history: it consumes `agent.history_limit` slots and steers subsequent
  interactive answers. It also widens the concurrency race in P0-4.
- **Approach:** run proactive prompts in a separate history namespace, e.g.
  `chat_id = f"{target}#proactive"`, while still *sending* to `target`. Consider
  a `share_history: bool = False` parameter on `notify_agent` for callers who
  *want* shared context.
- **Acceptance:** test that `notify_agent` does not append to the interactive
  chat's history (inspect `orchestrator._histories`); docs updated in
  `docs/REFERENCE.md` (Proactive messaging section) and
  `docs/WRITING_TOOLS.md` (proactive section).

### P0-3: Default notify target is arbitrary when multiple users are allowed

- **Type:** bug
- **Where:** `src/remotetoolbox/chat/telegram.py` (`default_to=next(iter(self.allowed), None)`)
  and `src/remotetoolbox/config.py` (`allowed_user_ids` returns a `set[int]`).
- **Problem:** `allowed` is a set, so with more than one allowed user the
  "default" recipient is whichever id iterates first — not "your first allowed
  user" as `docs/WRITING_TOOLS.md` claims. A digest could go to the wrong
  household member.
- **Approach:** preserve config order — add an ordered accessor (e.g.
  `allowed_user_ids_ordered: list[int]` parsed from the comma-separated string,
  keeping the set for membership checks) and use its first element for
  `default_to`. Keep docs claim accurate ("the first id listed in
  `RTB_ALLOWED_USERS`").
- **Acceptance:** test that ordering follows the config string (e.g. "222,111"
  → default 222); membership checks unchanged; docs verified accurate.

---

## P1 — hardening (small, contained; bundle with P0 if convenient)

### P1-1: Per-chat lock — proactive and interactive turns can interleave

- **Type:** bug (race)
- **Where:** `src/remotetoolbox/orchestrator.py` (`_histories`, `handle`).
- **Problem:** incoming Telegram updates are processed sequentially (PTB
  default), but a `notify_agent` scheduled from a tool's background thread runs
  *concurrently* with an in-flight `handle()` for the same chat id. Both append
  to the same unlocked history list mid-loop, interleaving tool/assistant
  messages and confusing the model. (P0-2 reduces the overlap but doesn't
  eliminate same-id concurrency.)
- **Approach:** `self._locks: dict[str, asyncio.Lock]` keyed like `_histories`;
  `handle()` acquires the chat's lock around the loop. Keep it simple — no
  global lock, no queueing semantics.
- **Acceptance:** test that two concurrent `handle()` calls for the same chat id
  serialize (e.g. a fake backend that yields control and asserts history
  consistency); concurrent calls for *different* chat ids still overlap.

### P1-2: Tool execution has no timeout

- **Type:** robustness
- **Where:** `src/remotetoolbox/tooling/loader.py` (`Toolset.call`).
- **Problem:** a tool that hangs (network call with no timeout) wedges its chat
  forever — and because updates process sequentially, it wedges *all* chats.
- **Approach:** wrap execution in `asyncio.wait_for` with a configurable
  `tools.call_timeout` (suggest default 60s; `0` = disabled). On timeout return
  text in the established style: `Error: tool <name> timed out after <n>s.`
  Note: a timed-out *sync* tool thread can't be killed — document that the
  result is abandoned, not cancelled.
- **Acceptance:** test with a slow async tool and a tiny timeout; new config key
  documented in `docs/CONFIGURATION.md` (the sync guard will force this) and the
  new error string added to `docs/REFERENCE.md`'s error table.

### P1-3: CI claims vs reality — mypy is never run

- **Type:** process
- **Where:** `.github/workflows/ci.yml`, `CLAUDE.md` ("Run `ruff check` and
  `mypy src` if available"), `pyproject.toml` (mypy in dev extras).
- **Problem:** type rot accumulates invisibly; agents are told mypy matters but
  nothing enforces it.
- **Approach:** add `mypy src` as a CI step. Expect to fix the errors it
  surfaces first (keep that diff focused; `# type: ignore` with a reason is
  acceptable where third-party stubs are missing). If the team prefers not to
  gate on it, instead remove the claim from CLAUDE.md — pick one, don't leave
  the mismatch.
- **Acceptance:** CI green with mypy step (or claim removed); no unexplained
  ignores.

---

## P2 — quality of life / operability

### P2-1: `remotetoolbox doctor` — manual preflight check

- **Type:** feature (small)
- **Where:** new subcommand in `src/remotetoolbox/__main__.py` (pattern:
  `init-tools`); logic in a new `doctor.py`.
- **Problem:** the most common support cases are environmental: Ollama down,
  model not pulled, empty token, empty allowlist, tools dir missing. A manual
  check answers "why doesn't it work?" in one command. (Note: an *automatic*
  startup warning was explicitly declined — this must be opt-in/manual only.)
- **Approach:** check and report, one line each: config file found + parses;
  `GET {host}/api/tags` reachable; configured model present in the tag list;
  if `chat.adapter: telegram` — token non-empty and `allowed_users` non-empty;
  each `tools.paths` entry exists; count of discovered tools. Exit non-zero if
  any check fails.
- **Acceptance:** tests for the pass/fail paths (mock the Ollama endpoint);
  documented in `docs/DEPLOYMENT.md` (troubleshooting points to it) and
  `docs/REFERENCE.md` CLI table.

### P2-2: Ollama client knobs — timeout and retry

- **Type:** robustness
- **Where:** `src/remotetoolbox/llm/ollama.py` (`httpx.Timeout(120.0, connect=10.0)`).
- **Problem:** the 120s request timeout is hardcoded; transient connection blips
  fail a whole turn with no retry.
- **Approach:** add `llm.ollama.request_timeout` (default 120) and a single
  cheap retry on `httpx.ConnectError`/`ReadTimeout` (not on HTTP-status errors).
  Don't add a retry library — keep it one loop.
- **Acceptance:** config keys documented (sync guard enforces); test that a
  first-call `ConnectError` followed by success returns the reply.

### P2-3: Drop `requirements.txt` (duplication drift)

- **Type:** cleanup
- **Where:** `requirements.txt` duplicates `pyproject.toml` deps and will drift.
- **Approach:** delete it; grep docs for references and point everything at
  `pip install -e .` / extras. If a pin-file is wanted later, generate it, don't
  hand-maintain it.
- **Acceptance:** no references to requirements.txt remain (docs-sync link guard
  plus a grep).

### P2-4: Guard REFERENCE error strings against drift

- **Type:** test
- **Where:** `tests/test_docs_sync.py`; `docs/REFERENCE.md` error table.
- **Problem:** config keys and links are guard-railed, but the error-message
  table is hand-maintained — a reworded error in code silently invalidates the
  doc (and the doc's promise is "search it for any error string you hit").
- **Approach:** parse the error table's first-column strings; for each, strip
  placeholders (`<x>`, `…`, format specifiers) down to a distinctive literal
  fragment and assert that fragment appears in `src/remotetoolbox/**/*.py`.
  Mark genuinely-runtime strings (e.g. produced by PTB) as exempt via a small
  allowlist in the test.
- **Acceptance:** test fails when an error string in code is reworded without
  updating the table (demonstrate via a temporary mutation in the PR
  description, not committed).

### P2-5: Clean up accumulated `sys.path` entries

- **Type:** cleanup (cosmetic)
- **Where:** `src/remotetoolbox/tooling/loader.py` (`_import_file` appends each
  tool dir, never removes).
- **Approach:** record appended paths during a scan; after `load_tools`
  completes imports, they can stay (helpers may import lazily at call time — so
  removing is *not* safe). Instead: dedupe, and remove stale entries from
  *previous* scans if `load_tools` is called more than once in a process.
  Honestly the smallest correct fix is to track what the loader added and only
  re-add what the current scan needs.
- **Acceptance:** repeated `load_tools` calls don't grow `sys.path` unboundedly;
  sibling-helper imports (see `tests/test_loader.py`) still pass — including a
  helper imported lazily inside a tool function body.

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
  `concurrent_updates=True` + P1-1's locks).
- `⚠️ {exc}` error replies may include host URLs — accepted; documented in
  `docs/SECURITY.md`.
- Proactive-notify spam risk from a hostile/buggy tool — documented in
  `docs/SECURITY.md` (P3-6 is the optional mitigation).
- In-memory history loss on restart — documented in `docs/ARCHITECTURE.md`
  (P3-4 is the optional change).
