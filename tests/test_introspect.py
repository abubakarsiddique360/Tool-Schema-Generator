from __future__ import annotations

from pathlib import Path

import pytest

from tool_schema_generator.introspect import IntrospectionError, describe_functions, split_docstring

EXAMPLES = Path(__file__).resolve().parent.parent / "examples" / "tools.py"

DOC = '''"""Fake module."""


def greet(name: str, times: int = 2, *, upper: bool = False) -> str:
    """Say hello.

    Args:
        name: Who to greet.
        times: How many times to repeat the greeting, which is a long
            description that wraps onto a second line.
        upper: Whether to shout.

    Returns:
        The greeting.
    """
    return name
'''


@pytest.fixture
def specs():
    return describe_functions(EXAMPLES.read_text(encoding="utf-8"))


def test_summary_and_parameter_descriptions() -> None:
    summary, parameters = split_docstring(
        "Do a thing.\n\nSecond summary line.\n\nArgs:\n    value: The value.\n    other: Another."
    )
    assert summary == "Do a thing. Second summary line."
    assert parameters == {"value": "The value.", "other": "Another."}


def test_sphinx_style_descriptions() -> None:
    _summary, parameters = split_docstring("Do a thing.\n\n:param value: The value.\n:param other: Another.")
    assert parameters["value"] == "The value."
    assert parameters["other"] == "Another."


def test_returns_section_stops_parameter_parsing() -> None:
    _summary, parameters = split_docstring("Do.\n\nArgs:\n    a: first.\n\nReturns:\n    something")
    assert parameters == {"a": "first."}


def test_wrapped_descriptions_are_joined() -> None:
    _summary, parameters = split_docstring("Do.\n\nArguments:\n    a: one\n        two")
    assert parameters["a"] == "one two"


def test_empty_docstring() -> None:
    assert split_docstring("") == ("", {})


def test_public_functions_are_described(specs) -> None:
    assert [spec.name for spec in specs] == ["get_weather", "search_docs", "send_email"]
    assert specs[0].description == "Return the current weather for a city."
    assert specs[2].returns == "bool"


def test_private_functions_are_skipped(specs) -> None:
    assert "_internal_helper" not in [spec.name for spec in specs]
    assert "_internal_helper" in [
        spec.name for spec in describe_functions(EXAMPLES.read_text(encoding="utf-8"), include_private=True)
    ]


def test_parameter_metadata(specs) -> None:
    weather = specs[0]
    city, units = weather.parameters
    assert city.required is True
    assert city.annotation == "str"
    assert units.default == "'celsius'"
    assert units.required is False
    assert units.description == "Which unit to report the temperature in."
    assert weather.required == ("city",)


def test_keyword_only_parameters_are_kept(specs) -> None:
    search = specs[1]
    assert [parameter.name for parameter in search.parameters] == ["query", "limit", "tags"]
    tags = search.parameters[2]
    assert tags.kind == "keyword"
    assert tags.default == "None"
    assert tags.required is False


def test_varargs_are_never_required() -> None:
    specs = describe_functions("def f(*args: int, **kwargs: str) -> None:\n    '''Doc.'''\n")
    kinds = {parameter.name: parameter.kind for parameter in specs[0].parameters}
    assert kinds == {"args": "var_positional", "kwargs": "var_keyword"}
    assert specs[0].required == ()


def test_positional_only_parameters() -> None:
    specs = describe_functions("def f(a: int, /, b: int = 3) -> None:\n    '''Doc.'''\n")
    assert [parameter.name for parameter in specs[0].parameters] == ["a", "b"]
    assert specs[0].parameters[1].default == "3"


def test_defaults_are_matched_to_the_right_parameters() -> None:
    specs = describe_functions("def f(a: int, b: int, c: int = 1, d: int = 2) -> None:\n    '''Doc.'''\n")
    defaults = {parameter.name: parameter.default for parameter in specs[0].parameters}
    assert defaults == {"a": None, "b": None, "c": "1", "d": "2"}


def test_nested_and_lambda_definitions_are_ignored() -> None:
    specs = describe_functions("class A:\n    def method(self) -> None:\n        '''Doc.'''\n")
    assert specs == []


def test_syntax_error_is_reported() -> None:
    with pytest.raises(IntrospectionError, match="cannot parse"):
        describe_functions("def broken(:\n")


def test_parameter_as_dict(specs) -> None:
    payload = specs[0].parameters[0].as_dict()
    assert payload["name"] == "city"
    assert payload["required"] is True
    assert specs[0].as_dict()["returns"] == "str"
