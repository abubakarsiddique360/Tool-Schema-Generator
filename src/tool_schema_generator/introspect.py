"""Read a Python module and describe its public functions."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

SECTION_RE = re.compile(r"^(args|arguments|parameters)\s*:?\s*$", re.IGNORECASE)
PARAM_RE = re.compile(r"^(?P<name>\*{0,2}[A-Za-z_][A-Za-z0-9_]*)\s*(?:\((?P<type>[^)]*)\))?\s*:\s*(?P<text>.+)$")
SPHINX_RE = re.compile(r"^:param\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*:\s*(?P<text>.+)$")
STOP_SECTIONS = ("returns", "return", "raises", "yields", "examples", "example", "note", "notes")


class IntrospectionError(ValueError):
    """Raised when a module cannot be parsed."""


@dataclass(frozen=True)
class Parameter:
    name: str
    annotation: str = ""
    default: str | None = None
    description: str = ""
    kind: str = "positional"

    @property
    def required(self) -> bool:
        return self.default is None and self.kind not in {"var_positional", "var_keyword"}

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "annotation": self.annotation,
            "default": self.default,
            "required": self.required,
            "description": self.description,
        }


@dataclass(frozen=True)
class FunctionSpec:
    name: str
    description: str
    parameters: tuple[Parameter, ...] = ()
    returns: str = ""
    module: str = ""

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(parameter.name for parameter in self.parameters if parameter.required)

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "returns": self.returns,
            "parameters": [parameter.as_dict() for parameter in self.parameters],
        }


def split_docstring(docstring: str) -> tuple[str, dict[str, str]]:
    """Return the summary line and a mapping of parameter name to its description."""
    lines = [line.rstrip() for line in docstring.strip().splitlines()]
    if not lines:
        return "", {}

    summary: list[str] = []
    descriptions: dict[str, str] = {}
    in_arguments = False
    current: str | None = None

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower().rstrip(":")
        if SECTION_RE.match(stripped):
            in_arguments = True
            current = None
            continue
        if in_arguments and lowered in STOP_SECTIONS:
            in_arguments = False
            current = None
            continue
        if in_arguments:
            argument = PARAM_RE.match(stripped)
            if argument:
                current = argument.group("name").lstrip("*")
                descriptions[current] = argument.group("text").strip()
                continue
            if current and stripped:
                descriptions[current] = f"{descriptions[current]} {stripped}".strip()
            continue
        if not summary:
            if stripped:
                summary.append(stripped)
        elif stripped and not stripped.endswith(":") and not SPHINX_RE.match(stripped):
            summary.append(stripped)

    for line in lines:
        sphinx = SPHINX_RE.match(line.strip())
        if sphinx:
            descriptions.setdefault(sphinx.group("name"), sphinx.group("text").strip())

    return " ".join(summary).strip(), descriptions


def _parameters(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[Parameter, ...]:
    arguments = node.args
    positional = [*arguments.posonlyargs, *arguments.args]
    defaults: list[str | None] = [None] * (len(positional) - len(arguments.defaults))
    defaults += [ast.unparse(default) for default in arguments.defaults]

    collected: list[Parameter] = []
    for argument, default in zip(positional, defaults, strict=True):
        collected.append(
            Parameter(
                name=argument.arg,
                annotation=ast.unparse(argument.annotation) if argument.annotation else "",
                default=default,
                kind="positional",
            )
        )

    if arguments.vararg is not None:
        collected.append(Parameter(name=arguments.vararg.arg, kind="var_positional"))

    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
        collected.append(
            Parameter(
                name=argument.arg,
                annotation=ast.unparse(argument.annotation) if argument.annotation else "",
                default=ast.unparse(default) if default is not None else None,
                kind="keyword",
            )
        )

    if arguments.kwarg is not None:
        collected.append(Parameter(name=arguments.kwarg.arg, kind="var_keyword"))

    return tuple(collected)


def describe_functions(source: str, include_private: bool = False) -> list[FunctionSpec]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise IntrospectionError(f"cannot parse the module: {exc.msg}") from exc

    specs: list[FunctionSpec] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        if not include_private and node.name.startswith("_"):
            continue
        summary, descriptions = split_docstring(ast.get_docstring(node) or "")
        parameters = tuple(
            Parameter(
                name=parameter.name,
                annotation=parameter.annotation,
                default=parameter.default,
                description=descriptions.get(parameter.name, ""),
                kind=parameter.kind,
            )
            for parameter in _parameters(node)
        )
        specs.append(
            FunctionSpec(
                name=node.name,
                description=summary,
                parameters=parameters,
                returns=ast.unparse(node.returns) if node.returns else "",
            )
        )
    return specs
