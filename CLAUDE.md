# CLAUDE.md — guidance for AI assistants working in this repo

This file orients Claude Code (and other coding agents) so you can extend
RemoteToolbox correctly without reading the whole codebase. Humans: this doubles
as a contributor cheat-sheet.

## What this project is

A self-hosted framework: **chat frontend → local LLM (Ollama) → user-written
tools**. The repo ships **framework + docs only**. Users' actual tools and all
credentials are gitignored and never committed.

## The #1 task: "add a tool that does X"

This is what most users will ask. Do exactly this:

1. Create `tools/<name>/tool.py` (the `tools/` dir is gitignored — that's
   correct and intended; the file is for the user's machine, not for committing).
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

Full details: [`docs/WRITING_TOOLS.md`](docs/WRITING_TOOLS.md). Copyable
examples: [`examples/tools/`](examples/tools/).

### Do NOT, when adding a tool:

- Don't commit anything under `tools/` or any secret — see "Git rules" below.
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
├── llm/               LLMBackend interface + Ollama backend
├── chat/              ChatAdapter interface + console/telegram adapters
└── tooling/           tool discovery (loader) + optional external MCP client
tools/                 USER tools live here — GITIGNORED
examples/tools/        committed, copyable example tools
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
  credential. `.gitignore` enforces this — keep it that way. If you introduce a
  new secret/tool location, add it to `.gitignore` in the same change.
- Quick check before committing:
  ```bash
  git ls-files | grep -E 'tools/(?!README|\.gitkeep)|\.env$|config\.yaml$' || echo clean
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

## When unsure

Read [`orchestrator.py`](src/remotetoolbox/orchestrator.py) first — it's short
and shows how everything connects. Then the relevant `base.py`. Prefer extending
via the documented extension points over modifying the core loop.
