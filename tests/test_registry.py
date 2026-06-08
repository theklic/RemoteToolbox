"""Tests for the tool registry and schema generation — the stable contract.

Run with:  pytest
"""

from __future__ import annotations

from typing import Optional

import pytest

from remotetoolbox.registry import build_parameters_schema, clear_registry, tool


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_basic_registration():
    from remotetoolbox.registry import REGISTRY

    @tool(description="Add two numbers.")
    def add(a: int, b: int) -> int:
        return a + b

    assert "add" in REGISTRY
    spec = REGISTRY["add"]
    assert spec.description == "Add two numbers."
    assert spec.parameters["required"] == ["a", "b"]
    assert spec.parameters["properties"]["a"] == {"type": "integer"}


def test_description_defaults_to_docstring():
    from remotetoolbox.registry import REGISTRY

    @tool
    def greet(name: str) -> str:
        """Greet a person warmly."""
        return name

    assert REGISTRY["greet"].description == "Greet a person warmly."


def test_optional_and_default_not_required():
    def fn(city: str, units: Optional[str] = None, limit: int = 5):
        ...

    schema = build_parameters_schema(fn)
    assert schema["required"] == ["city"]
    assert "units" not in schema.get("required", [])
    assert schema["properties"]["limit"] == {"type": "integer"}


def test_list_and_dict_types():
    def fn(items: list[str], meta: dict):
        ...

    schema = build_parameters_schema(fn)
    assert schema["properties"]["items"] == {"type": "array", "items": {"type": "string"}}
    assert schema["properties"]["meta"] == {"type": "object"}


def test_param_doc_becomes_description():
    def fn(city: str):
        """Look up weather.

        city: The city to look up.
        """
        ...

    schema = build_parameters_schema(fn)
    assert schema["properties"]["city"]["description"] == "The city to look up."


def test_duplicate_name_raises():
    @tool
    def dup():
        ...

    with pytest.raises(ValueError, match="Duplicate tool name"):

        @tool(name="dup")
        def other():
            ...


def test_ollama_tool_format():
    @tool(description="Echo.")
    def echo(text: str) -> str:
        return text

    from remotetoolbox.registry import REGISTRY

    rendered = REGISTRY["echo"].to_ollama_tool()
    assert rendered["type"] == "function"
    assert rendered["function"]["name"] == "echo"
    assert rendered["function"]["parameters"]["properties"]["text"] == {"type": "string"}
