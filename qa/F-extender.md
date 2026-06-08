# QA Findings — Extending the Framework (persona: Jordan)

Status: complete

Scope: Can a developer add a new LLM backend and a new chat adapter using ONLY
docs/ARCHITECTURE.md, docs/CHAT_ADAPTERS.md, docs/REFERENCE.md — without reading core source?

## Task 1 — New LLM backend (scripted, tool-calling loop)

RESULT: SUCCESS end-to-end. Built `ScriptedBackend(LLMBackend)` in
`/tmp/jordan/scripted_backend.py` + real `@tool` echo in `/tmp/jordan/tools/echo_tool.py`,
drove a full orchestrator round trip (`/tmp/jordan/drive_loop.py`):
```
loaded tools: ['echo']
REPLY: The tool said: ECHO:HI
backend calls: 2
```
Backend emitted a `ToolCall(id, name, arguments)` on call 1; orchestrator ran the
real tool, appended a role="tool" message, backend produced final text on call 2.

Contract verification (all MATCH reality, src/remotetoolbox/llm/base.py):
- `async def chat(self, messages: list[LLMMessage], tools: list[dict] | None = None) -> LLMMessage` — exact match.
- `async def aclose(self) -> None` default no-op — match.
- `ToolCall(id: str, name: str, arguments: dict)` — match.
- `LLMMessage(role, content="", tool_calls=[], name=None)` fields — match.
- On the forced final round the orchestrator calls `chat(messages, tools=None)` — confirmed
  in source (orchestrator.py:95); my backend's recorded `tools` arg was a real list on the
  tool round, matching "or `None` ... on the forced final round".

### F1 [Blocker→Major] Orchestrator constructor is undocumented; doc-only build fails
Severity: Major (Blocker for "drive the loop directly", but adapters normally get the
orchestrator pre-built via `assemble()`, so it's Major in practice).
Evidence: NONE of the three extender docs give the `Orchestrator.__init__` signature.
REFERENCE "orchestrator loop" documents only `handle/reset/aclose`. My documented-best-guess
`Orchestrator(backend=..., toolset=...)` raised:
`TypeError: Orchestrator.__init__() got an unexpected keyword argument 'backend'`.
I HAD TO READ orchestrator.py to find the real signature:
`Orchestrator(llm, toolset, agent_config, llm_runtime)`.
Surprises a doc reader would not predict:
  - param is `llm`, not `backend`.
  - requires an `agent_config: AgentConfig` AND `llm_runtime: OllamaConfig`.
  - `max_tool_rounds` lives on **OllamaConfig**, so even a NON-Ollama backend must be
    handed an `OllamaConfig` just to get the round budget. That coupling is undocumented
    and counterintuitive for someone adding a non-Ollama backend.
Suggested fix: Document the Orchestrator constructor in REFERENCE (it's a public-ish
collaborator), and/or rename `llm_runtime`'s type away from `OllamaConfig` (e.g. a
backend-agnostic `RuntimeConfig`) so `max_tool_rounds` isn't Ollama-branded.

### F2 [Nit] Doc dataclass `tool_calls: list[ToolCall] = []` is not valid Python
REFERENCE "LLMMessage / ToolCall" shows `tool_calls: list[ToolCall] = []`. Real source
correctly uses `field(default_factory=list)`. A literal mutable `[]` default in a
@dataclass raises `ValueError: mutable default ...`. Harmless for understanding, but a
reader who mirrors the snippet verbatim hits an error. Suggest showing `= field(default_factory=list)`.

## Task 2 — New chat adapter (scripted/stdin)

RESULT: SUCCESS. Pasted the docs/CHAT_ADAPTERS.md "Template" (the DiscordAdapter
skeleton) verbatim and adapted it to a "scripted" adapter in
`/tmp/jordan/scripted_adapter.py`; drove it via `/tmp/jordan/drive_adapter.py`:
```
CAPTURED REPLIES: ['The tool said: ECHO:HI']
```
The documented serve()/_serve() pattern runs AS WRITTEN:
- `serve()` is sync/blocking, calls `asyncio.run(self._serve())`.
- `_serve()` does `self.orchestrator = await self._assemble()` INSIDE the loop,
  then `try: ...client... finally: await self.orchestrator.aclose()`.
- `await self.orchestrator.handle(chat_id, text)` returns the reply string.
All match `chat/console.py` (the real reference adapter) and `chat/base.py`.

The loop-binding caveat ("build the orchestrator inside the adapter's own loop so
loop-bound resources stay on the right loop") is CORRECT and clearly stated in
both CHAT_ADAPTERS.md and ARCHITECTURE.md (#why-adapters-expose-a-blocking-serve).
`__main__.py:_make_assembler` confirms `assemble` is exactly a
`Callable[[], Awaitable[Orchestrator]]` (the `Assemble` type alias in base.py).

### F3 [Nit] Template `__init__(self, config, assemble)` works but is under-explained
The docs' base contract is `__init__(self, assemble)`, yet the template overrides
it as `__init__(self, config, assemble)` and the factory section calls it as
`DiscordAdapter(config.discord, assemble)`. This is fine (each adapter defines its
own __init__ and calls `super().__init__(assemble)`), and it ran correctly for me.
But the docs never say WHY the override is allowed/needed, and a careful reader may
worry the base signature is being violated. Suggest a one-line note: "Adapters may
take extra constructor args (e.g. their config block); just forward `assemble` to
`super().__init__`."  Severity Nit — did not block me.

### F4 [Nit] No standalone way to build `assemble` shown for adapter testing
To exercise serve() in isolation I needed an `assemble` factory, but no doc shows
how to construct an Orchestrator (same root cause as F1). I mirrored
`__main__.py:_make_assembler` after reading source. The CHAT_ADAPTERS template
assumes `self._assemble` already exists (it does, in production, via the entry
point) — so for the normal "add an adapter and run the whole app" path this is a
non-issue. It only bites when unit-testing an adapter standalone.

## Task 3 — Registration patterns (build_backend / build_adapter)

Verified by reading the factories and constructing the documented error paths
(could not edit tracked files, so confirmed slot-in compatibility instead).

ADAPTER registration (docs/CHAT_ADAPTERS.md "Register it in the factory") is
ACCURATE:
- `build_adapter(config: ChatConfig, assemble: Assemble) -> ChatAdapter` — my
  `ScriptedAdapter(config, assemble)` matches the documented branch shape
  `return DiscordAdapter(config.discord, assemble)`.
- Unknown-name error matches REFERENCE error table EXACTLY:
  `Unknown chat.adapter 'scripted'. Built-in options: 'console', 'telegram'. See docs/CHAT_ADAPTERS.md.`
- The docs DO tell you to also add a `discord:` block to `config.py` — correct;
  `ChatConfig` fields are `['adapter', 'telegram']`, so a new adapter's config
  block must be added there or it won't be reachable.

BACKEND registration is ACCURATE but DOCS ARE INCOMPLETE — see F5.
- `build_backend(config: LLMConfig) -> LLMBackend` — my `ScriptedBackend()`
  return type matches.
- Unknown-name error matches REFERENCE EXACTLY:
  `Unknown llm.backend 'scripted'. Built-in option: 'ollama'. See docs/ARCHITECTURE.md to add one.`

### F5 [Major] Backend docs omit the required config.py edit (silent-drop trap)
Severity: Major. For chat adapters the docs explicitly say to add a config block
to `config.py`. For LLM backends, NEITHER ARCHITECTURE.md nor REFERENCE.md says
to touch `config.py` — they only say "Register a new backend in
`llm/__init__.py:build_backend`." But `LLMConfig` fields are ONLY
`['backend', 'ollama']`, and pydantic `extra` is unset (default = ignore). I
verified:
```
LLMConfig(backend='scripted', scripted={'foo': 1})  ->  the `scripted` block is
silently DROPPED (no error).
```
So a developer who follows the backend docs and puts `scripted:` settings in
config.yaml gets them silently swallowed; their backend can't read its host/model/
key. They must ALSO edit `config.py` to add a sub-config field — undocumented for
backends. Worse, `max_tool_rounds` lives on `OllamaConfig`, so the entry point
passes `config.llm.ollama` as `llm_runtime` even for a non-Ollama backend (see F1).
Suggested fix: in ARCHITECTURE/REFERENCE backend section, mirror the adapter
instructions — "add a matching `<name>:` block to `LLMConfig` in config.py" — and
move `max_tool_rounds` off `OllamaConfig` to a backend-neutral config so non-Ollama
backends aren't forced through Ollama config. (Optionally set pydantic
`extra='forbid'` so a misplaced block errors loudly instead of being dropped.)

## Task 4 — Doc sufficiency

Could Jordan do this WITHOUT reading core source? PARTIALLY.

Places I HAD to read source because the extender docs were insufficient:
1. `Orchestrator.__init__` signature — undocumented in all three extender docs
   (F1). Needed for BOTH tasks (to drive the loop in Task 1 and to write an
   `assemble` factory in Task 2). Found in orchestrator.py + __main__.py.
2. How to write an `assemble` factory at all (F4) — only `__main__.py:_make_assembler`
   shows it. The adapter docs assume it's handed to you.
3. The config wiring for a new backend (F5) — had to inspect `LLMConfig`/`config.py`
   to discover a sub-block is required and silently dropped otherwise.

Doc examples that fail / mislead if pasted:
- REFERENCE `tool_calls: list[ToolCall] = []` is invalid as a real dataclass
  default (F2) — cosmetic, source uses `field(default_factory=list)`.
- The CHAT_ADAPTERS template itself runs fine as pasted (good).

Contracts the docs describe ACCURATELY (verified against source + runtime):
- `LLMBackend.chat(messages, tools=None) -> LLMMessage` signature — exact.
- `aclose()` optional no-op — exact; orchestrator calls `llm.aclose()` then
  `toolset.aclose()`.
- `tools=None` on the forced final round — confirmed (orchestrator.py:95).
- `LLMMessage`/`ToolCall` field names & types — exact (modulo F2 cosmetic).
- `ChatAdapter`: serve() blocking, `_assemble` async factory, build inside the
  loop, `handle(chat_id, text)` per message, `reset(chat_id)` optional — all exact.
- Both factory unknown-name error strings — byte-for-byte match REFERENCE.

## Verdict

YES — a developer CAN extend RemoteToolbox at both documented extension points
from the docs, and the happy-path templates/contracts are accurate (the chat
adapter template runs verbatim; all backend/adapter/message signatures and factory
error strings match reality). BUT the docs have real gaps that force source-reading
and one silent-failure trap:
- The `Orchestrator` constructor is undocumented (F1) — needed to drive/test.
- The backend docs omit the required `config.py` edit and a misplaced config block
  is silently dropped (F5) — a developer following the backend docs literally gets
  a backend that can't read its own settings.
- `max_tool_rounds` being Ollama-branded couples every backend to OllamaConfig.

Findings: 5 total — Major: 2 (F1, F5) · Nit: 3 (F2, F3, F4). No Blockers (every
task ultimately succeeded), but F1+F5 cost real source-reading and would trip up a
strict doc-only developer.

TOP 3 FIXES:
1. Document `Orchestrator.__init__(llm, toolset, agent_config, llm_runtime)` in
   REFERENCE.md (and show a minimal `assemble` factory). [F1/F4]
2. In the BACKEND docs, mirror the adapter instructions: add a `<name>:` sub-block
   to `LLMConfig` in config.py; ideally set pydantic `extra='forbid'` so a
   misplaced block errors instead of being silently dropped. [F5]
3. Move `max_tool_rounds` off `OllamaConfig` to a backend-neutral runtime config so
   non-Ollama backends aren't coupled to Ollama config. [F1/F5]
