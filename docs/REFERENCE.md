# Reference

The exact contracts: signatures, behaviors, limits, and error messages. This is
the "look it up" layer — for when a guide isn't specific enough or a coding agent
needs an authoritative answer. Each section points at the source file so you can
verify.

**Contents**
- [`@tool` decorator](#the-tool-decorator)
- [Schema generation rules](#schema-generation-rules)
- [`ToolSpec`](#toolspec)
- [Tool discovery rules](#tool-discovery-rules)
- [`Toolset` (calling tools)](#toolset)
- [LLM backend contract](#llm-backend-contract)
- [`LLMMessage` / `ToolCall`](#llmmessage--toolcall)
- [The orchestrator loop](#the-orchestrator-loop)
- [Chat adapter contract](#chat-adapter-contract)
- [Proactive messaging (`notify`)](#proactive-messaging)
- [Factories & entry point](#factories--entry-point)
- [Error & message reference](#error--message-reference)

---

## The `@tool` decorator

Source: [`registry.py`](../src/remotetoolbox/registry.py). Imported as
`from remotetoolbox import tool`. **This is the stable public API** — tool files
depend on it, so its behavior is kept backwards-compatible.

```python
def tool(
    _func=None,
    *,
    name: str | None = None,
    description: str | None = None,
    parameters: dict | None = None,
): ...
```

| Param | Default | Meaning |
|---|---|---|
| `name` | function name | The tool name shown to the model. **Must be unique** across all loaded tools. |
| `description` | first line of the docstring | One-line summary the model reads to decide whether to call it. |
| `parameters` | auto-generated from the signature | Explicit JSON Schema (`object`) to bypass auto-generation. |

Behavior:

- Works as `@tool` **and** `@tool(...)`.
- Returns the **original function unchanged** — it stays normally callable/testable.
- Registers a [`ToolSpec`](#toolspec) into the process-global `REGISTRY` dict
  (keyed by name) at **import time**.
- A duplicate name raises `ValueError` immediately *within a single file*. A name
  that collides with a tool from an **already-loaded** file instead makes that
  file fail to import — the loader logs it and skips it (the first tool wins); it
  is not a hard crash. See [tool discovery](#tool-discovery-rules).

Example with an explicit schema (for constraints type hints can't express):

```python
@tool(
    name="set_timer",
    description="Start a countdown timer.",
    parameters={
        "type": "object",
        "properties": {"minutes": {"type": "integer", "minimum": 1, "maximum": 180}},
        "required": ["minutes"],
    },
)
def set_timer(minutes: int) -> str: ...
```

---

## Schema generation rules

When you don't pass `parameters=`, the schema is built from the signature by
`build_parameters_schema()`. Exact rules:

- Iterates the function's parameters. **Skips** `self`/`cls` and
  `*args`/`**kwargs` (variadics can't be described to the model).
- Maps each parameter's type hint to a JSON Schema type:

  | Python annotation | JSON Schema |
  |---|---|
  | `str` | `{"type": "string"}` |
  | `int` | `{"type": "integer"}` |
  | `float` | `{"type": "number"}` |
  | `bool` | `{"type": "boolean"}` |
  | `list[T]` / `set` / `tuple` | `{"type": "array", "items": <schema of T>}` |
  | `dict` | `{"type": "object"}` |
  | `Optional[T]` / `Union[T, None]` | schema of `T` |
  | other `Union` / unknown / no hint | `{}` (unconstrained) |

- **Required** = parameters with no default **and** not `Optional`. Everything
  else is omitted from `required`.
- **Per-argument descriptions** come from docstring lines of the form
  `name: description` (see gotcha below). Attached as the field's `description`.
- Result shape: `{"type": "object", "properties": {...}, "required": [...]}`
  (`required` omitted when empty).

**Description fallback:** if `description=` isn't given, the first non-empty line
of the docstring is used; if there's no docstring, the function name with
underscores turned into spaces.

> **Gotcha — docstring `word: text` lines.** Any line like `note: see below` is
> parsed as a `name: description` pair (case-sensitively). It's only *applied* if
> `name` exactly matches a real parameter, so stray lines are harmless — a
> capitalized `Returns:` won't collide with a `returns` parameter. The only real
> hazard is a lowercase line whose key is literally one of your parameter names.
> Keep argument doc lines clean: `city: the city name`.

---

## `ToolSpec`

Source: [`registry.py`](../src/remotetoolbox/registry.py). The normalized record
the rest of the system uses.

| Field | Type | Notes |
|---|---|---|
| `name` | str | Unique tool name. |
| `description` | str | Shown to the model. |
| `parameters` | dict | JSON Schema (`object`). |
| `func` | callable | The underlying function. |
| `is_async` | bool | `True` if `func` is a coroutine function. |
| `source` | str | Where it came from (e.g. `mcp:<server>`); not used for equality. |

Method: `to_ollama_tool()` → renders the OpenAI/Ollama `tools` entry:
`{"type": "function", "function": {"name", "description", "parameters"}}`.

---

## Tool discovery rules

Source: [`tooling/loader.py`](../src/remotetoolbox/tooling/loader.py). At startup,
`load_tools(config.tools)`:

1. Clears the registry (so reloads are clean).
2. For each path in `tools.paths`, scans **recursively** for `*.py` files.
3. **Skips** files whose name starts with `_`, and anything inside a hidden
   directory (`.git`, `.venv`, …) or a vendored one (`__pycache__`,
   `node_modules`, `site-packages`, …). This lets a tools directory safely be its
   own git repo or contain a virtualenv. Use `_helper.py` for shared code you
   don't want scanned. See [MANAGING_TOOLS.md](MANAGING_TOOLS.md).
4. Imports each remaining file as a standalone module (by file path — no
   packaging needed), which runs its `@tool` decorators.
5. A file that fails to import is **logged and skipped** — it doesn't crash
   startup; the other tools still load. (Run with `logging.level: DEBUG` to see
   each file loaded.)
6. Snapshots the registry into a [`Toolset`](#toolset).
7. If `tools.mcp_servers` is set, connects them and merges their tools. **Local
   tools win** on a name collision (the MCP tool is skipped with a warning).

Changes to tool files take effect on **restart** only — discovery runs once.

---

## `Toolset`

Source: [`tooling/loader.py`](../src/remotetoolbox/tooling/loader.py). Holds the
loaded `ToolSpec`s and knows how to call them.

| Method | Returns | Notes |
|---|---|---|
| `ollama_tools()` | `list[dict]` | All tools in Ollama format (passed to the backend). |
| `names()` | `list[str]` | Loaded tool names. |
| `await call(name, arguments)` | `str` | Invoke a tool; **always returns a string**. |
| `await aclose()` | — | Releases MCP sessions if any. |

`call()` semantics (important — tools never crash the agent):

- Unknown name → returns `Error: no tool named '<name>'. Available: …`.
- **Async** tools are awaited; **sync** tools run via `asyncio.to_thread` so
  blocking I/O doesn't stall the chat loop.
- A call exceeding `tools.call_timeout` (default 60s; `0` disables) → returns
  `Error: tool <name> timed out after <n>s.` An async tool is cancelled; a sync
  tool's thread can't be killed, so it keeps running but its result is abandoned.
- `TypeError` (bad arguments) → returns `Error calling <name>: bad arguments (…)`.
- Any other exception → caught, logged with traceback, returns
  `Error: tool <name> failed: <exc>`.
- Return-value stringification: `None` → `"Done."`; `str` → itself; anything
  else → JSON (`json.dumps(..., default=str)`), falling back to `str()`.

The error text is fed back to the model so it can recover or apologize.

---

## LLM backend contract

Source: [`llm/base.py`](../src/remotetoolbox/llm/base.py). Implement this to add a
model server.

```python
class LLMBackend(ABC):
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[dict] | None = None,
    ) -> LLMMessage: ...

    async def aclose(self) -> None: ...   # optional; default no-op
```

- `chat()` returns the assistant's next message, which **may contain
  `tool_calls`**. `tools` are OpenAI/Ollama-format specs (or `None` when no tools
  are available, or on the forced final round).
- **Register** a new backend in two places (same pattern as a chat adapter):
  1. add a branch to `llm/__init__.py:build_backend` returning your class;
  2. add a settings sub-block to `LLMConfig` in
     [`config.py`](../src/remotetoolbox/config.py) (e.g. an `openai: OpenAIConfig`
     field) so your `config.yaml` block is parsed. **A config block with no
     matching model field is silently ignored**, so this step is required for
     your backend to read its settings.

The shipped **Ollama** backend ([`llm/ollama.py`](../src/remotetoolbox/llm/ollama.py))
posts to `POST {host}/api/chat` with `stream=false`, translates to/from the wire
format, synthesizes IDs for tool calls, and tolerates `arguments` arriving as a
JSON string. Network/HTTP failures surface as `RuntimeError` (see
[errors](#error--message-reference)).

---

## `LLMMessage` / `ToolCall`

Source: [`llm/base.py`](../src/remotetoolbox/llm/base.py). The normalized message
types the orchestrator speaks (backends translate to/from their wire format).

```python
from dataclasses import dataclass, field

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class LLMMessage:
    role: str                 # "system" | "user" | "assistant" | "tool"
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    name: str | None = None   # tool name, when role == "tool"
```

---

## The orchestrator loop

Source: [`orchestrator.py`](../src/remotetoolbox/orchestrator.py).

**Constructor** (you build one in an adapter's `assemble` factory, or when
testing a backend directly):

```python
Orchestrator(
    llm,            # an LLMBackend (the parameter is `llm`, not `backend`)
    toolset,        # a Toolset (from load_tools)
    agent_config,   # config.agent (AgentConfig: system_prompt, history_limit,
                    #               max_tool_rounds) — backend-neutral
)
```

> A minimal `assemble` factory (mirroring
> [`__main__.py`](../src/remotetoolbox/__main__.py)):
>
> ```python
> async def assemble() -> Orchestrator:
>     toolset = await load_tools(config.tools)
>     llm = MyBackend(...)
>     return Orchestrator(llm, toolset, config.agent)
> ```

One public method drives everything:

```python
async def handle(chat_id: str, user_text: str) -> str
```

Algorithm:

1. Append the user message to that `chat_id`'s in-memory history.
2. Build `messages = [system_prompt, *history]`.
3. Loop up to `max_tool_rounds + 1` times:
   - Ask the backend with the tool list.
   - Append the reply to history.
   - **No `tool_calls`** → trim history, return `reply.content`.
   - Otherwise run each tool call via `Toolset.call`, append each result as a
     `tool` message, and loop.
4. If the round budget is exhausted, make **one final call with `tools=None`**
   to force a text answer, and return that.

Other methods:

| Method | Effect |
|---|---|
| `reset(chat_id)` | Drops that chat's history (used by `/reset`). |
| `await aclose()` | Closes the LLM backend and toolset. |

State & limits:

- History is **in-memory**, **per `chat_id`**, lost on restart.
- Trimmed to `agent.history_limit`; trimming never leaves a leading `tool`
  message (which would dangle without its assistant call).
- `chat_id` is supplied by the adapter (`"console"` for the console;
  the Telegram chat ID as a string for Telegram) — keep it stable per
  conversation so histories don't mix.

---

## Chat adapter contract

Source: [`chat/base.py`](../src/remotetoolbox/chat/base.py). Implement this to add
a frontend. Full walkthrough in [CHAT_ADAPTERS.md](CHAT_ADAPTERS.md).

```python
class ChatAdapter(ABC):
    def __init__(self, assemble: Assemble) -> None: ...
    def serve(self) -> None: ...   # blocking; owns its own event loop
```

- `serve()` is **synchronous/blocking** — each adapter runs whatever event loop
  its chat library needs.
- `self._assemble` is an **async factory** that builds the `Orchestrator`; call
  it **inside** the adapter's own loop and store the result on
  `self.orchestrator`, so loop-bound resources (the Ollama HTTP client, MCP
  sessions) live on the right loop. (See `telegram.py`'s `post_init` for the
  "library owns the loop" pattern.)
- Register a new adapter in `chat/__init__.py:build_adapter`.
- **Mind platform message limits.** Telegram rejects messages over 4,096 chars;
  the adapter splits replies and outbound `notify` sends into chunks (preferring
  newline boundaries) via `_chunks()`. A new adapter should do the equivalent for
  its platform so long replies/digests don't silently fail.

---

## Proactive messaging

Source: [`messaging.py`](../src/remotetoolbox/messaging.py). The primitive that
lets a tool send a message **outbound / unprompted** (digests, alerts). Public:
`from remotetoolbox import notify, notify_agent`.

```python
notify(text: str, to: str | int | None = None) -> concurrent.futures.Future
notify_agent(prompt: str, to: str | int | None = None, *, share_history: bool = False) -> concurrent.futures.Future
```

- `notify` delivers `text` to chat `to` via the active adapter. `notify_agent`
  first runs `prompt` through the orchestrator (tools + LLM) and sends the reply.
- `notify_agent` runs the prompt in a **separate** conversation
  (id `"<to>#proactive"`) so a scheduled digest doesn't pollute or get confused by
  the user's interactive history. Pass `share_history=True` to share it instead.
- `to` defaults to the adapter's default chat (Telegram: the **first id listed in
  `allowed_users`** — config order, not set order; console: `"console"`). Missing
  target → `RuntimeError`.
- **Fire-and-forget and thread-safe** — the call schedules delivery on the
  adapter's event loop (via `run_coroutine_threadsafe`) and returns immediately,
  so it's safe from a tool's background thread. The returned `Future` lets a
  non-loop thread `.result()` to confirm/await; delivery errors are logged and
  exposed on the Future (never raised into the tool).
- Requires a **running** adapter; called otherwise → `RuntimeError`
  ("no active messenger"). The adapter wires this up at startup via
  `messaging.configure(...)` and clears it on shutdown.

The framework provides only the send; scheduling/triggering is the tool's job.
Guide + a self-scheduling example: [WRITING_TOOLS.md](WRITING_TOOLS.md#proactive-messages-digests-alerts).

---

## Factories & entry point

| Function | Source | Purpose |
|---|---|---|
| `load_config(config_path=None, env_path=None)` | `config.py` | Load `.env` + `config.yaml` → `Config`. |
| `build_backend(llm_config)` | `llm/__init__.py` | `LLMConfig` → `LLMBackend`. |
| `build_adapter(chat_config, assemble)` | `chat/__init__.py` | `ChatConfig` → `ChatAdapter`. |
| `load_tools(tools_config)` | `tooling/__init__.py` | Discover tools → `Toolset` (async). |
| `main()` | `__main__.py` | CLI entry: parse args, load config, set up logging, build adapter, `serve()`. |

CLI:

| Invocation | Does |
|---|---|
| `python -m remotetoolbox [-c PATH] [--env PATH]` | Run the chat agent (default). |
| `python -m remotetoolbox init-tools <path> [--no-git]` | Scaffold a personal tools repo from `examples/tools-repo` (copy + `git init` + first commit). See [MANAGING_TOOLS.md](MANAGING_TOOLS.md). `--no-git` copies files only. |
| `python -m remotetoolbox doctor` | Preflight check (Ollama reachable + model pulled, Telegram token/allowlist, tools paths, discovered tool count). Exits non-zero if any check fails. Implemented in [`doctor.py`](../src/remotetoolbox/doctor.py). |

(`remotetoolbox` is also installed as a console script equivalent to
`python -m remotetoolbox`.) `init-tools` is implemented in
[`scaffold.py`](../src/remotetoolbox/scaffold.py); it refuses to write into a
non-empty directory and never fails the scaffold if the git commit can't be made.

---

## Error & message reference

Exact strings the app emits, what they mean, and the fix. (Search this section
for the text you saw.)

| Message (substring) | Source | Meaning & fix |
|---|---|---|
| `Could not reach Ollama at <host>: … Is \`ollama serve\` running and the model pulled?` | `llm/ollama.py` | Ollama unreachable. Start `ollama serve`; verify `OLLAMA_HOST`; confirm the model is pulled. |
| `Ollama returned <code>: <body>` | `llm/ollama.py` | Ollama responded with an HTTP error. Common: model name wrong/not pulled (`ollama pull <model>`), or the model doesn't support tools. |
| `Unknown llm.backend '<x>'. Built-in option: 'ollama'. …` | `llm/__init__.py` | `llm.backend` typo, or a backend you haven't registered. Use `ollama` or add one. |
| `Unknown chat.adapter '<x>'. Built-in options: 'console', 'telegram'. …` | `chat/__init__.py` | `chat.adapter` typo, or an unregistered adapter. |
| `Telegram adapter selected but TELEGRAM_BOT_TOKEN is empty. …` | `chat/telegram.py` | `adapter: telegram` but no token. Set `TELEGRAM_BOT_TOKEN` in `.env`. |
| `RTB_ALLOWED_USERS is empty: the bot will refuse EVERYONE. …` (warning) | `chat/telegram.py` | The bot starts but rejects all users. Add your numeric Telegram ID to `RTB_ALLOWED_USERS`. |
| `⛔ Not authorized.` (to the user) | `chat/telegram.py` | The sender's ID isn't in the allowlist. |
| `Duplicate tool name '<x>' (already defined by …).` | `registry.py` | Two tools share a name. Rename one or pass `name=` to disambiguate. |
| `MCP servers configured but the 'mcp' package is not installed. Run: pip install -e ".[mcp]"` | `tooling/mcp_client.py` | You set `tools.mcp_servers` without the extra. Install it. |
| `Tools directory <dir> does not exist (skipping).` (warning) | `tooling/loader.py` | A path in `tools.paths` is missing. Create it or fix the path. |
| `Failed to import tool file <path> (skipping)` (logged) | `tooling/loader.py` | A tool file errored on import. Run with `logging.level: DEBUG`; fix the file's import/syntax. |
| `Error: no tool named '<x>'. Available: …` (to the model) | `tooling/loader.py` | The model called a tool that isn't loaded. Usually a hallucinated name or a file that didn't load. |
| `Error calling <x>: bad arguments (…)` (to the model) | `tooling/loader.py` | The model passed wrong arguments. Tighten the tool's `description`/types so the schema is clearer. |
| `Error: tool <x> failed: <exc>` (to the model) | `tooling/loader.py` | The tool raised. Check logs for the traceback. |
| `Error: tool <x> timed out after <n>s.` (to the model) | `tooling/loader.py` | The tool exceeded `tools.call_timeout`. Give it its own internal timeout, or raise the limit. |

For symptom-based ("the bot won't reply") troubleshooting, see
[DEPLOYMENT.md → Troubleshooting](DEPLOYMENT.md#troubleshooting).
