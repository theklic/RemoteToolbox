# Configuration reference

Every setting RemoteToolbox reads, where it comes from, its type, and its
default. This mirrors the models in
[`src/remotetoolbox/config.py`](../src/remotetoolbox/config.py) — if they ever
disagree, the code wins (and this doc should be fixed).

## How configuration is loaded

There are **two** sources, by design:

| Source | Holds | Committed? |
|---|---|---|
| **`config.yaml`** | Non-secret settings (which model, which chat app, …) | No — copy from `config.example.yaml` |
| **`.env`** | Secrets (tokens, API keys) | No — copy from `.env.example` |

`config.yaml` may reference environment variables with `${VAR}`; they are
expanded from the environment (which `.env` populates) at load time. This is how
secrets reach the config without ever being written into `config.yaml`.

> **Unknown keys are rejected.** Config models are strict (`extra="forbid"`), so a
> typo'd or misplaced key (e.g. a backend block under the wrong parent) raises a
> validation error at startup instead of being silently ignored. Put each key
> under the right section (see the tables below).

```yaml
chat:
  telegram:
    token: ${TELEGRAM_BOT_TOKEN}   # value comes from .env / the environment
```

### Resolution order (which config file is used)

`load_config()` picks the config file from, in order:

1. The `--config` CLI flag (`python -m remotetoolbox --config path.yaml`)
2. The `RTB_CONFIG` environment variable
3. `./config.yaml`
4. If none exists → **built-in defaults** (the app still runs)

The `.env` file defaults to `./.env`, overridable with `--env`.

### `${VAR}` expansion rules

- Pattern: `${NAME}` where `NAME` matches `[A-Z0-9_]+` (uppercase, digits,
  underscore).
- Expanded **recursively** through strings, lists, and dicts in the YAML.
- An **undefined** variable expands to an **empty string** (not an error). A
  blank `token:` or `allowed_users:` is usually the real cause of "nothing
  works" — check your `.env`. ⚠️ Because of this, a `${VAR}` reference in
  `config.yaml` **overrides the field's built-in default with empty** when the
  variable is unset — e.g. `host: ${OLLAMA_HOST}` resolves to `""`, *not*
  `http://localhost:11434`, if `OLLAMA_HOST` isn't set. Keep referenced vars
  defined in `.env` (the shipped `.env.example` pre-fills `OLLAMA_HOST`).
- Lowercase or mixed-case `${var}` is **not** expanded. Use uppercase env names.

---

## `config.yaml` keys

Types and defaults are authoritative. All keys are optional; omitted keys use the
default shown.

### `chat`

| Key | Type | Default | Description |
|---|---|---|---|
| `chat.adapter` | string | `console` | Which frontend to run. Built-in: `console`, `telegram`. Unknown values raise at startup. |
| `chat.telegram.token` | string | `""` | Telegram bot token. Use `${TELEGRAM_BOT_TOKEN}`. Required when `adapter: telegram`. |
| `chat.telegram.allowed_users` | string | `""` | Comma-separated Telegram numeric user IDs allowed to chat. **Empty = nobody** (safe default). Use `${RTB_ALLOWED_USERS}`. |

> Only the block for the **active** adapter needs to be valid. With
> `adapter: console`, the `telegram` block is ignored.

### `llm`

| Key | Type | Default | Description |
|---|---|---|---|
| `llm.backend` | string | `ollama` | Model backend. Built-in: `ollama`. Unknown values raise at startup. |
| `llm.ollama.host` | string | `http://localhost:11434` | Base URL of the Ollama server. Use `${OLLAMA_HOST}`. |
| `llm.ollama.model` | string | `llama3.1` | Model name. **Must support tool calling** (e.g. `llama3.1`, `qwen2.5`, `mistral-nemo`). |
| `llm.ollama.options` | map | `{}` | Passed straight to Ollama's `options` (e.g. `temperature`, `num_ctx`, `top_p`). See Ollama docs. |

### `agent`

| Key | Type | Default | Description |
|---|---|---|---|
| `agent.system_prompt` | string | `"You are RemoteToolbox, a helpful self-hosted assistant."` | Prepended to every conversation. Keep it short and concrete; it steers tool use. |
| `agent.history_limit` | int | `20` | Messages kept per chat (in memory). Older messages drop off; trimming never leaves a dangling `tool` message first. |
| `agent.max_tool_rounds` | int | `6` | Max tool-call → result → model rounds per user message before a forced final answer. Backend-neutral. See [Reference → orchestrator loop](REFERENCE.md#the-orchestrator-loop). |

### `tools`

| Key | Type | Default | Description |
|---|---|---|---|
| `tools.paths` | list[string] | `["./tools"]` | Directories scanned **recursively** for `@tool` functions. `~` is expanded; may point at a separate tools repo anywhere on disk (see [Managing Tools](MANAGING_TOOLS.md)). Hidden/vendored dirs are skipped — see [Reference → tool discovery](REFERENCE.md#tool-discovery-rules). |
| `tools.call_timeout` | float | `60.0` | Seconds before a single tool call is abandoned (`0` = no limit). Stops one hung tool from wedging a chat. See [Reference → Toolset](REFERENCE.md#toolset). |
| `tools.mcp_servers` | list | `[]` | External MCP servers to connect (optional; needs the `mcp` extra). |
| `tools.mcp_servers[].name` | string | — | Label for the server (required). |
| `tools.mcp_servers[].command` | string | — | Executable to launch (required), e.g. `npx`. |
| `tools.mcp_servers[].args` | list[string] | `[]` | Arguments for the command. |
| `tools.mcp_servers[].env` | map | `{}` | Extra environment variables for the server process. |

### `logging`

| Key | Type | Default | Description |
|---|---|---|---|
| `logging.level` | string | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`. `DEBUG` logs each tool module loaded and each tool call. `httpx`/`httpcore` are pinned to `WARNING` regardless. |

---

## Environment variables (`.env`)

| Variable | Used by | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | `config.yaml` → `chat.telegram.token` | Token from @BotFather. |
| `RTB_ALLOWED_USERS` | `config.yaml` → `chat.telegram.allowed_users` | Comma-separated allowed Telegram user IDs. |
| `OLLAMA_HOST` | `config.yaml` → `llm.ollama.host` | Where Ollama is reachable. |
| `RTB_CONFIG` | `load_config()` | Path to the config file (resolution step 2). |
| *(your own)* | your tools | Tools read their own secrets via `os.environ` — add whatever they need. |

> `.env` only populates the process environment. A variable referenced by
> `${VAR}` in `config.yaml` must be **set in `.env`** (or the real environment)
> to have any effect.

---

## Worked examples

### Minimal — console, defaults

An **empty** `config.yaml` is valid; everything falls back to defaults
(`console` adapter, `ollama` at `localhost:11434`, model `llama3.1`, tools from
`./tools`). Good for a first run.

### Telegram on a home server

`.env`:

```
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
RTB_ALLOWED_USERS=11111111,22222222
OLLAMA_HOST=http://localhost:11434
```

`config.yaml`:

```yaml
chat:
  adapter: telegram
  telegram:
    token: ${TELEGRAM_BOT_TOKEN}
    allowed_users: ${RTB_ALLOWED_USERS}
llm:
  ollama:
    model: qwen2.5
    options:
      temperature: 0.3
    max_tool_rounds: 8
agent:
  system_prompt: >
    You are my home assistant. Prefer calling a tool over guessing. Be brief.
tools:
  paths:
    - ./tools
logging:
  level: INFO
```

### Multiple tool folders + an external MCP server

```yaml
tools:
  paths:
    - ./tools
    - ./shared-tools
  mcp_servers:
    - name: filesystem
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/srv/shared"]
      env:
        SOME_FLAG: "1"
```

---

## Adding your own config keys

If you fork to add an adapter or backend that needs settings, add a pydantic
model in [`config.py`](../src/remotetoolbox/config.py) and reference it from the
relevant parent model. Because `Config.model_validate` runs on the
env-expanded dict, your new fields get `${VAR}` expansion and validation for
free. Document the new keys here in the same change.
