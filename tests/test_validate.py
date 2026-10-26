from __future__ import annotations

from pathlib import Path

from tool_schema_generator.introspect import describe_functions
from tool_schema_generator.schema import module_schema
from tool_schema_generator.validate import validate_document, validate_tool

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "tools.py"

GOOD_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Return the current weather.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}


def messages(problems) -> list[str]:
    return [problem.message for problem in problems]


def test_generated_schema_is_valid() -> None:
    payload = module_schema(describe_functions(EXAMPLES.read_text(encoding="utf-8")))
    assert validate_document(payload) == []


def test_good_tool_passes() -> None:
    assert validate_tool(GOOD_TOOL) == []


def test_tool_must_be_an_object() -> None:
    assert messages(validate_tool("nope")) == ["a tool must be an object"]


def test_type_must_be_function() -> None:
    assert "'type' must be 'function'" in messages(validate_tool({"type": "tool", "function": {}}))


def test_missing_function_block() -> None:
    assert messages(validate_tool({"type": "function"})) == ["missing 'function' object"]


def test_name_rules() -> None:
    broken = {
        "type": "function",
        "function": {"name": "has space", "description": "d", "parameters": {"type": "object", "properties": {}}},
    }
    assert "must match ^[A-Za-z0-9_-]{1,64}$" in messages(validate_tool(broken))


def test_description_is_required() -> None:
    broken = {
        "type": "function",
        "function": {"name": "ok", "description": "  ", "parameters": {"type": "object", "properties": {}}},
    }
    assert "a description is required" in messages(validate_tool(broken))


def test_long_description_is_rejected() -> None:
    broken = {
        "type": "function",
        "function": {"name": "ok", "description": "x" * 2000, "parameters": {"type": "object", "properties": {}}},
    }
    assert "longer than 1024 characters" in messages(validate_tool(broken))


def test_parameters_must_be_an_object_schema() -> None:
    broken = {"type": "function", "function": {"name": "ok", "description": "d", "parameters": {"type": "array"}}}
    assert "must be 'object'" in messages(validate_tool(broken))


def test_missing_parameters() -> None:
    assert "missing 'parameters' object" in messages(
        validate_tool({"type": "function", "function": {"name": "ok", "description": "d"}})
    )


def test_required_must_be_declared() -> None:
    broken = {
        "type": "function",
        "function": {
            "name": "ok",
            "description": "d",
            "parameters": {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["b"]},
        },
    }
    assert "'b' is not a declared property" in messages(validate_tool(broken))


def test_required_must_be_a_list() -> None:
    broken = {
        "type": "function",
        "function": {
            "name": "ok",
            "description": "d",
            "parameters": {"type": "object", "properties": {}, "required": "a"},
        },
    }
    assert "must be a list" in messages(validate_tool(broken))


def test_properties_need_a_type_or_enum() -> None:
    broken = {
        "type": "function",
        "function": {"name": "ok", "description": "d", "parameters": {"type": "object", "properties": {"a": {}}}},
    }
    assert "property needs a 'type' or an 'enum'" in messages(validate_tool(broken))


def test_unknown_type_is_reported() -> None:
    broken = {
        "type": "function",
        "function": {
            "name": "ok",
            "description": "d",
            "parameters": {"type": "object", "properties": {"a": {"type": "money"}}},
        },
    }
    assert "unknown type 'money'" in messages(validate_tool(broken))


def test_arrays_need_items() -> None:
    broken = {
        "type": "function",
        "function": {
            "name": "ok",
            "description": "d",
            "parameters": {"type": "object", "properties": {"a": {"type": "array"}}},
        },
    }
    assert "array properties need an 'items' schema" in messages(validate_tool(broken))


def test_nullable_type_list_is_allowed() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "ok",
            "description": "d",
            "parameters": {"type": "object", "properties": {"a": {"type": ["string", "null"]}}},
        },
    }
    assert validate_tool(tool) == []


def test_enum_is_allowed_without_type() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "ok",
            "description": "d",
            "parameters": {"type": "object", "properties": {"a": {"enum": ["x"]}}},
        },
    }
    assert validate_tool(tool) == []


def test_enum_must_be_a_list() -> None:
    tool = {
        "type": "function",
        "function": {
            "name": "ok",
            "description": "d",
            "parameters": {"type": "object", "properties": {"a": {"type": "string", "enum": "x"}}},
        },
    }
    assert "'enum' must be a list" in messages(validate_tool(tool))


def test_document_accepts_a_single_tool() -> None:
    assert validate_document(GOOD_TOOL) == []


def test_document_rejects_unknown_shapes() -> None:
    assert messages(validate_document({"hello": "world"})) == ["expected {'tools': [...]} or a single tool object"]


def test_empty_tool_list_is_reported() -> None:
    assert messages(validate_document({"tools": []})) == ["no tools to validate"]


def test_document_paths_point_at_the_failing_tool() -> None:
    payload = {"tools": [GOOD_TOOL, dict(GOOD_TOOL, type="nope")]}
    problems = validate_document(payload, path="file.json")
    assert problems[0].path == "file.json.tools[1]"
    assert problems[0].as_dict()["message"] == "'type' must be 'function'"
    assert str(problems[0]).startswith("file.json.tools[1]:")
