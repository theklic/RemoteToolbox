"""The tool registry: the ``@tool`` decorator and JSON-schema generation.

This is the *stable public contract* tool authors depend on. A tool is just a
Python function decorated with ``@tool``. The decorator inspects the function's
type hints and docstring to build the JSON schema the LLM needs in order to call
it, then registers it in a process-global registry that the loader reads.

Keep this module dependency-light and backwards compatible — people's tools
import from here.
"""

from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass, field
from typing import Any, Callable, get_args, get_origin, get_type_hints

__all__ = ["tool", "ToolSpec", "REGISTRY", "clear_registry"]


@dataclass
class ToolSpec:
    """Everything the orchestrator needs to expose and invoke one tool."""

    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema (object) describing the arguments
    func: Callable[..., Any]
    is_async: bool = False
    source: str = field(default="", compare=False)  # file it was loaded from

    def to_ollama_tool(self) -> dict[str, Any]:
        """Render in the OpenAI/Ollama ``tools`` format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# Process-global registry. The loader imports tool modules, which populate this
# via the decorator, then the loader snapshots it.
REGISTRY: dict[str, ToolSpec] = {}


def clear_registry() -> None:
    """Reset the registry (used by the loader between scans and by tests)."""
    REGISTRY.clear()


# --- JSON schema generation --------------------------------------------------

# Minimal, readable Python-type -> JSON-schema-type mapping. Tool authors who
# need richer schemas can pass an explicit ``parameters=`` to @tool.
_PRIMITIVES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
}


def _schema_for_annotation(annotation: Any) -> dict[str, Any]:
    """Best-effort JSON schema for a single parameter annotation."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}  # unconstrained

    origin = get_origin(annotation)

    # Optional[X] / Union[X, None] -> schema for X (None handled via 'required').
    if origin is typing.Union:
        non_none = [a for a in get_args(annotation) if a is not type(None)]
        if len(non_none) == 1:
            return _schema_for_annotation(non_none[0])
        return {}  # genuinely ambiguous union; leave open

    if annotation in _PRIMITIVES:
        return {"type": _PRIMITIVES[annotation]}

    if origin in (list, set, tuple) or annotation in (list, set, tuple):
        args = get_args(annotation)
        item_schema = _schema_for_annotation(args[0]) if args else {}
        return {"type": "array", "items": item_schema or {}}

    if origin is dict or annotation is dict:
        return {"type": "object"}

    # Unknown / custom type: don't constrain it.
    return {}


def _is_optional(annotation: Any) -> bool:
    return get_origin(annotation) is typing.Union and type(None) in get_args(annotation)


def build_parameters_schema(func: Callable[..., Any]) -> dict[str, Any]:
    """Build an ``object`` JSON schema from a function's signature.

    Parameters without defaults are marked required. Docstring text after a line
    of the form ``param_name: description`` is attached as the field description.
    """
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    param_docs = _parse_param_docs(func.__doc__ or "")

    properties: dict[str, Any] = {}
    required: list[str] = []

    for pname, param in sig.parameters.items():
        if pname in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue  # *args/**kwargs can't be described to the model

        annotation = hints.get(pname, param.annotation)
        schema = _schema_for_annotation(annotation)
        if pname in param_docs:
            schema = {**schema, "description": param_docs[pname]}
        properties[pname] = schema

        if param.default is inspect.Parameter.empty and not _is_optional(annotation):
            required.append(pname)

    result: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


def _parse_param_docs(doc: str) -> dict[str, str]:
    """Extract ``name: description`` lines from a docstring (lightweight)."""
    docs: dict[str, str] = {}
    for line in doc.splitlines():
        stripped = line.strip()
        if ":" in stripped and not stripped.endswith(":"):
            key, _, val = stripped.partition(":")
            key = key.strip()
            if key.isidentifier():
                docs[key] = val.strip()
    return docs


def _short_description(func: Callable[..., Any]) -> str:
    """First non-empty line of the docstring, used when no description is given."""
    doc = (func.__doc__ or "").strip()
    return doc.splitlines()[0].strip() if doc else func.__name__.replace("_", " ")


# --- The decorator -----------------------------------------------------------


def tool(
    _func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    parameters: dict[str, Any] | None = None,
) -> Callable[..., Any]:
    """Register a function as a tool the agent can call.

    Usage::

        @tool(description="Get the weather for a city.")
        def get_weather(city: str) -> str:
            ...

    Args:
        name: Override the tool name (defaults to the function name). Must be
            unique across all loaded tools.
        description: What the tool does, shown to the LLM. Defaults to the first
            line of the docstring.
        parameters: Provide an explicit JSON schema to bypass auto-generation
            (use when your signature can't be expressed with simple type hints).

    The original function is returned unchanged, so it stays normally callable.
    """

    def wrap(func: Callable[..., Any]) -> Callable[..., Any]:
        tool_name = name or func.__name__
        spec = ToolSpec(
            name=tool_name,
            description=description or _short_description(func),
            parameters=parameters or build_parameters_schema(func),
            func=func,
            is_async=inspect.iscoroutinefunction(func),
        )
        if tool_name in REGISTRY:
            existing = REGISTRY[tool_name]
            raise ValueError(
                f"Duplicate tool name {tool_name!r} "
                f"(already defined by {existing.source or existing.func.__module__})."
            )
        REGISTRY[tool_name] = spec
        return func

    # Support both @tool and @tool(...).
    if _func is not None:
        return wrap(_func)
    return wrap
