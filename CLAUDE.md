# CLAUDE.md — guidance for AI assistants working in this repo

This file orients Claude Code (and other coding agents) so you can extend
RemoteToolbox correctly without reading the whole codebase. Humans: this doubles
as a contributor cheat-sheet.

## What this project is

A self-hosted framework: **chat frontend → local LLM (Ollama) → user-written
tools**. The repo ships **framework + docs only**. Users' actual tools and all
credentials are gitignored and never committed.

> **This does NOT mean "don't create tools here."** Tools you write **go in the
> `./tools/` directory and run from there** — that's the one correct place for
> them. The directory is gitignored *on purpose* so the user's private tools stay
> off GitHub; the framework still loads them from `./tools/` at startup.
> **Gitignored = private, not off-limits.** "Never commit tools" means don't
> `git add`/commit them — it does **not** mean don't create them. (If you find
> yourself avoiding `./tools/`, you've read this backwards.)

## The #1 task: "add a tool that does X"

This is what most users will ask. Do exactly this:

1. Create the file at `tools/<name>/tool.py` — **yes, really under `tools/`.**
   That dir is gitignored (so the tool stays private and you won't — and
   shouldn't — `git add` it), but the file must exist there because that's where
   RemoteToolbox discovers tools at startup. Creating it is correct; committing
   it is not.
2. Write a function decorated with `@tool` from `remotetoolbox`:

   ```python
   from remotetoolbox import tool

   @tool(description="<concrete one-line description of what it does>")
   def <name>(<typed args>) -> str:
       """<summary>

       <arg>: <what it is>
       """
       ...
       return "<short, clear result>"
   ```

3. **Type-hint every parameter** (drives the LLM's JSON schema).
4. Add a docstring line `arg_name: description` for each argument.
5. **Read secrets from `os.environ`**, never hardcode them. Tell the user to add
   the variable to `.env` (also gitignored).
6. Return a short string (or a JSON-able `dict`/`list`).
7. Tell the user to **restart** RemoteToolbox (tools load at startup) and how to
   test it in the console adapter (`python -m remotetoolbox`).

For **proactive** tools (digests, alerts), a tool can push a message unprompted
with `from remotetoolbox import notify, notify_agent` — `notify(text)` sends text
you composed; `notify_agent(prompt)` lets the agent compose it. The framework
only sends; the tool owns when/why (no built-in scheduler). See
[`docs/WRITING_TOOLS.md`](docs/WRITING_TOOLS.md#proactive-messages-digests-alerts).

Full details: [`docs/WRITING_TOOLS.md`](docs/WRITING_TOOLS.md). Copyable
examples: [`examples/tools/`](examples/tools/).

**If the user versions their tools** (there's a `CHANGELOG.md` in the tools
directory, or `tools.paths` points at a separate repo), add an entry to that
`CHANGELOG.md` — a new dated `## YYYY-MM-DD` heading as the template shows —
describing what you added/changed, and commit it to the **user's tools repo —
never this one**. To set up such a repo, point them at
`python -m remotetoolbox init-tools <path>`. See
[`docs/MANAGING_TOOLS.md`](docs/MANAGING_TOOLS.md).

### Do NOT, when adding a tool:

- Don't *commit* the tool — it lives under the gitignored `tools/` and stays
  there (see "Git rules"). This is about `git add`/commit only; the tool file
  **should** exist under `tools/`. Don't put it anywhere else, and don't skip
  creating it.
- Don't add a broad `run_shell(cmd)` / `exec(code)` tool unless the user
  explicitly asks and understands the risk (see [`docs/SECURITY.md`](docs/SECURITY.md)).
- Don't add heavy dependencies to the core; if a tool needs a library, the user
  installs it in their own environment.

## Project layout

```
src/remotetoolbox/
├── __main__.py        entry point; assembles + runs the adapter
├── config.py          pydantic config models; loads config.yaml + .env (${VAR} expansion)
├── registry.py        @tool decorator + JSON-schema generation  ← STABLE PUBLIC API
├── orchestrator.py    the agent loop (chat → LLM → tools → reply)
├── messaging.py       notify()/notify_agent() — proactive outbound messages  ← PUBLIC API
├── scaffold.py        `init-tools` — scaffolds a user's separate tools repo
├── llm/               LLMBackend interface + Ollama backend
├── chat/              ChatAdapter interface + console/telegram adapters
└── tooling/           tool discovery (loader) + optional external MCP client
tools/                 USER tools live here — GITIGNORED
examples/tools/        committed, copyable example tools
examples/tools-repo/   template for a user's own versioned tools repo
docs/                  architecture, writing tools, deployment, security, adapters
```

## The three extension points (each = a base class + a factory line)

| To add… | Implement | Register in |
|---|---|---|
| a capability (common) | a `@tool` function in `tools/` | nothing — auto-discovered |
| a model backend | `LLMBackend` in `llm/` | `llm/__init__.py:build_backend` |
| a chat frontend | `ChatAdapter` in `chat/` | `chat/__init__.py:build_adapter` |

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and
[`docs/CHAT_ADAPTERS.md`](docs/CHAT_ADAPTERS.md).

## Conventions

- **Python 3.10+**, `from __future__ import annotations` at the top of modules.
- Type hints everywhere; keep the public `@tool` API backwards-compatible.
- Async-first internals: `Orchestrator.handle`, `LLMBackend.chat`,
  `Toolset.call` are `async`. Sync tools are run in a thread automatically.
- Keep dependencies minimal. Core deps: `httpx`, `pydantic`, `pyyaml`,
  `python-dotenv`. Telegram and MCP are **optional extras**.
- Line length 100 (ruff). Run `ruff check` and `mypy src` if available.
- Errors from tools must be **caught and returned as text**, not raised to the
  user — the model should be able to recover.

## Running & testing

```bash
pip install -e ".[dev]"        # add ,telegram and/or ,mcp as needed
pytest                          # unit tests + docs-sync guards
python -m remotetoolbox         # console adapter, no tokens needed — fastest loop
```

When you change framework code, add/extend a test in `tests/`. The schema
generator and registry are the highest-value things to keep covered.

**Docs stay in sync automatically.** [`tests/test_docs_sync.py`](tests/test_docs_sync.py)
(run in CI via [`.github/workflows/ci.yml`](.github/workflows/ci.yml)) fails if:
- you add/rename/remove a config field without updating
  [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) (it checks the key **and** its
  default value), or
- any internal doc link / `#anchor` breaks (e.g. you rename a heading).

So if you touch `config.py`, contracts, or headings, expect to update the docs in
the **same change** — `pytest` will name exactly what's out of sync. The example
tools are also load-tested ([`tests/test_examples.py`](tests/test_examples.py)),
so keep them working when you change the `@tool` API.

## Git rules (important)

- Develop framework/doc changes normally and commit them.
- **Never commit** anything under `tools/`, `.env`, `config.yaml`, or any
  credential. `.gitignore` enforces this — keep it that way. (Creating tool files
  under `tools/` is expected and correct; they're gitignored, so they simply
  never get staged. "Don't commit" ≠ "don't create.") If you introduce a new
  secret/tool location, add it to `.gitignore` in the same change.
- Quick check before committing (prints `clean` when nothing private is tracked):
  ```bash
  git ls-files | grep -E '^tools/|^\.env$|^config\.yaml$' \
    | grep -vE '^tools/(README\.md|\.gitkeep)$' || echo clean
  ```
- Do not create pull requests unless the user explicitly asks.

## Where to look things up

These two reference docs are kept exact and greppable — check them before
reading source:

- [`docs/REFERENCE.md`](docs/REFERENCE.md) — every contract (`@tool`, schema
  rules, `LLMBackend`, `ChatAdapter`, the orchestrator loop) **and an
  error-message reference** (search it for any error string you hit).
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md) — every `config.yaml` key and
  env var, with types and defaults.

If you change a contract, default, or error message, update those two docs in the
**same commit** so they stay accurate.

## Picking up work

[`BACKLOG.md`](BACKLOG.md) is the prioritized work list (from project review),
written so an agent can take one item end-to-end: each has the problem, file
locations, approach, and acceptance criteria — plus decisions the owner has
already made (don't re-open those). Delete an item in the same PR that fixes it.

## When unsure

Read [`orchestrator.py`](src/remotetoolbox/orchestrator.py) first — it's short
and shows how everything connects. Then the relevant `base.py`. Prefer extending
via the documented extension points over modifying the core loop.
