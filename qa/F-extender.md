# QA Findings — Extending the Framework (persona: Jordan)

Status: in progress

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

## Task 3 — Registration patterns (build_backend / build_adapter)

## Task 4 — Doc sufficiency

## Verdict
