# Architecture

RemoteToolbox is small on purpose. Five moving parts, three of which are
extension points with tiny interfaces.

```
   ┌─────────────┐   user text    ┌──────────────────┐   LLMMessage    ┌─────────────┐
   │ ChatAdapter │ ─────────────► │   Orchestrator   │ ──────────────► │ LLMBackend  │
   │ (frontend)  │ ◄───────────── │   (agent loop)   │ ◄────────────── │  (Ollama)   │
   └─────────────┘   reply text   └──────────────────┘   reply +        └─────────────┘
                                       │      ▲          tool_calls
                              call(name, args) │ result
                                       ▼      │
                                  ┌──────────────────┐
                                  │     Toolset      │  ← your @tool functions in ./tools
                                  │  (+ MCP servers) │  ← optional external MCP servers
                                  └──────────────────┘
```

## The flow

1. A **ChatAdapter** (`console`, `telegram`, …) receives a user message and
   calls `orchestrator.handle(chat_id, text)`.
2. The **Orchestrator** appends the message to that chat's history, prepends the
   system prompt, and asks the **LLMBackend** for a reply, passing the JSON
   schemas of all available tools.
3. If the reply contains **tool calls**, the orchestrator runs each one against
   the **Toolset**, appends the results as `tool` messages, and loops back to
   step 2. This repeats up to `max_tool_rounds` times.
4. When the model replies with plain text (no tool calls), that text is returned
   to the adapter and shown to the user.

The whole loop lives in [`orchestrator.py`](../src/remotetoolbox/orchestrator.py)
and is under 100 lines. Read it — it's the best way to understand the system.

## The three extension points

Each is an abstract base class with a factory. To add an implementation, write
the class and add one line to the factory.

| Interface | File | Factory | Add one to… |
|-----------|------|---------|-------------|
| `LLMBackend` | [`llm/base.py`](../src/remotetoolbox/llm/base.py) | `llm/__init__.py:build_backend` | support a new model server |
| `ChatAdapter` | [`chat/base.py`](../src/remotetoolbox/chat/base.py) | `chat/__init__.py:build_adapter` | support a new chat frontend |
| `@tool` functions | your `./tools` dir | auto-discovered | add a capability (the common case) |

### Why adapters expose a blocking `serve()`

Different frontends have incompatible event-loop expectations — `python-telegram-bot`
insists on running its own loop via `run_polling()`, while the console runs a
plain `asyncio` loop. So `ChatAdapter.serve()` is **synchronous and blocking**;
each adapter owns its loop strategy internally. To keep loop-bound resources
(the Ollama HTTP client, MCP sessions) on the correct loop, adapters receive an
async `assemble()` factory and build the orchestrator *inside* their own loop
(see `__main__.py:_make_assembler`).

## Normalized messages

The orchestrator never sees Ollama's wire format. Backends translate to/from
[`LLMMessage`](../src/remotetoolbox/llm/base.py) (`role`, `content`,
`tool_calls`, `name`). This keeps the loop backend-agnostic and makes adding a
new backend a pure translation exercise.

## Tools: native vs. MCP

- **Native tools** are plain `@tool` Python functions discovered from `./tools`.
  This is the primary, simplest path — no packaging, no servers.
- **External MCP servers** can be listed in `config.yaml`; the optional
  [`mcp_client.py`](../src/remotetoolbox/tooling/mcp_client.py) launches them and
  surfaces their tools alongside your native ones. Use this to reuse existing
  MCP servers (filesystem, GitHub, home automation, …).

Both end up as `ToolSpec` objects in a single `Toolset`, so the LLM sees one
unified tool list and the orchestrator calls them the same way.

## State & lifecycle

- Conversation history is **in-memory, per `chat_id`**, trimmed to
  `agent.history_limit`. Restarting the process forgets conversations. (Want
  persistence? That's a natural fork point — swap the `_histories` dict for a
  store.)
- Tools are loaded **once at startup**. Add/change a tool → restart the process.
- Nothing is written to disk by the framework except logs.

## Proactive (outbound) messages

The flow above is reactive, but a tool can also push a message **unprompted** via
`notify()` / `notify_agent()` ([`messaging.py`](../src/remotetoolbox/messaging.py)).
At startup the active adapter registers a send function + its event loop with the
messaging module; `notify` schedules delivery onto that loop thread-safely (so a
tool's background timer can call it). There's deliberately **no scheduler** — the
tool owns the "when/why". See [REFERENCE.md](REFERENCE.md#proactive-messaging).

## What this is *not*

No multi-agent orchestration, no RAG, no web UI, no plugin marketplace. If you
need those, this is a clean base to build on, but the shipped scope is "a few
personal tools, reachable from chat, running locally."
