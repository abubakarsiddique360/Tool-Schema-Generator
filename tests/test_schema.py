from __future__ import annotations

from pathlib import Path

import pytest

from tool_schema_generator.introspect import Parameter, describe_functions
from tool_schema_generator.schema import function_schema, module_schema, parameter_schema, schema_for

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "tools.py"


@pytest.mark.parametrize(
    ("annotation", "expected"),
    [
        ("str", {"type": "string"}),
        ("int", {"type": "integer"}),
        ("float", {"type": "number"}),
        ("bool", {"type": "boolean"}),
        ("dict[str, int]", {"type": "object", "additionalProperties": {"type": "integer"}}),
        ("list[str]", {"type": "array", "items": {"type": "string"}}),
        (
            "list[dict[str, int]]",
            {"type": "array", "items": {"type": "object", "additionalProperties": {"type": "integer"}}},
        ),
        ("tuple[int, int]", {"type": "array", "items": {"type": "integer"}}),
        ("Path", {"type": "string"}),
        ("Whatever", {"type": "string"}),
        ("", {"type": "string"}),
        ("Literal['a', 'b']", {"enum": ["a", "b"], "type": "string"}),
        ("Literal[1, 2]", {"enum": [1, 2], "type": "integer"}),
    ],
)
def test_schema_for(annotation: str, expected: dict) -> None:
    assert schema_for(annotation) == expected


def test_optional_adds_null() -> None:
    assert schema_for("Optional[str]") == {"type": ["string", "null"]}
    assert schema_for("str | None") == {"type": ["string", "null"]}


def test_union_keeps_the_first_schema() -> None:
    assert schema_for("int | str") == {"type": ["integer", "string"]}
    assert schema_for("None") == {"type": "null"}


def test_union_of_containers_keeps_items() -> None:
    schema = schema_for("list[int] | None")
    assert schema["type"] == ["array", "null"]
    assert schema["items"] == {"type": "integer"}


def test_parameter_schema_includes_description_and_default() -> None:
    parameter = Parameter(name="limit", annotation="int", default="10", description="How many.")
    assert parameter_schema(parameter) == {"type": "integer", "description": "How many.", "default": 10}


def test_parameter_schema_defaults_are_typed() -> None:
    text = Parameter(name="label", annotation="str", default="'none'")
    assert parameter_schema(text)["default"] == "none"
    option = Parameter(name="tags", annotation="list[str] | None", default="None")
    schema = parameter_schema(option)
    assert schema["default"] is None
    assert schema["type"] == ["array", "null"]


def test_varargs_become_arrays() -> None:
    parameter = Parameter(name="args", annotation="int", kind="var_positional")
    assert parameter_schema(parameter) == {"type": "array", "items": {"type": "integer"}}


def test_function_schema_shape() -> None:
    specs = describe_functions(EXAMPLES.read_text(encoding="utf-8"))
    tool = function_schema(specs[0])
    assert tool["type"] == "function"
    function = tool["function"]
    assert function["name"] == "get_weather"
    assert function["parameters"]["type"] == "object"
    assert function["parameters"]["required"] == ["city"]
    assert function["parameters"]["properties"]["units"]["enum"] == ["celsius", "fahrenheit"]


def test_optional_parameters_are_not_required() -> None:
    specs = describe_functions(EXAMPLES.read_text(encoding="utf-8"))
    tool = function_schema(specs[2])
    assert tool["function"]["parameters"]["required"] == ["to", "subject", "body"]


def test_module_schema_lists_every_tool() -> None:
    specs = describe_functions(EXAMPLES.read_text(encoding="utf-8"))
    payload = module_schema(specs)
    assert [tool["function"]["name"] for tool in payload["tools"]] == ["get_weather", "search_docs", "send_email"]


def test_function_without_parameters_has_empty_properties() -> None:
    specs = describe_functions("def ping() -> str:\n    '''Ping the server.'''\n")
    tool = function_schema(specs[0])
    assert tool["function"]["parameters"] == {"type": "object", "properties": {}}
    assert "required" not in tool["function"]["parameters"]
