"""Validate a JSON tool schema document."""

from __future__ import annotations

import re
from dataclasses import dataclass

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ALLOWED_TYPES = frozenset({"string", "integer", "number", "boolean", "array", "object", "null"})
MAX_DESCRIPTION = 1024


@dataclass(frozen=True)
class Problem:
    path: str
    message: str

    def as_dict(self) -> dict:
        return {"path": self.path, "message": self.message}

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


def _check_property(name: str, schema: object, path: str) -> list[Problem]:
    problems: list[Problem] = []
    if not isinstance(schema, dict):
        return [Problem(path, "property schema must be an object")]

    declared = schema.get("type")
    if declared is None and "enum" not in schema:
        problems.append(Problem(path, "property needs a 'type' or an 'enum'"))
        return problems

    if declared is not None:
        types = [declared] if isinstance(declared, str) else list(declared) if isinstance(declared, list) else []
        if not types:
            problems.append(Problem(path, "'type' must be a string or a list of strings"))
        for type_name in types:
            if type_name not in ALLOWED_TYPES:
                problems.append(Problem(path, f"unknown type {type_name!r}"))
        if "array" in types and not isinstance(schema.get("items"), dict):
            problems.append(Problem(path, "array properties need an 'items' schema"))

    if "enum" in schema and not isinstance(schema["enum"], list):
        problems.append(Problem(path, "'enum' must be a list"))
    if "description" in schema and not isinstance(schema["description"], str):
        problems.append(Problem(path, "'description' must be a string"))
    if name in {"", " "}:
        problems.append(Problem(path, "property names cannot be blank"))
    return problems


def validate_tool(tool: object, path: str = "tool") -> list[Problem]:
    problems: list[Problem] = []
    if not isinstance(tool, dict):
        return [Problem(path, "a tool must be an object")]
    if tool.get("type") != "function":
        problems.append(Problem(path, "'type' must be 'function'"))

    function = tool.get("function")
    if not isinstance(function, dict):
        problems.append(Problem(f"{path}.function", "missing 'function' object"))
        return problems

    name = function.get("name")
    if not isinstance(name, str) or not NAME_RE.match(name):
        problems.append(Problem(f"{path}.function.name", "must match ^[A-Za-z0-9_-]{1,64}$"))

    description = function.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append(Problem(f"{path}.function.description", "a description is required"))
    elif len(description) > MAX_DESCRIPTION:
        problems.append(Problem(f"{path}.function.description", f"longer than {MAX_DESCRIPTION} characters"))

    parameters = function.get("parameters")
    if not isinstance(parameters, dict):
        problems.append(Problem(f"{path}.function.parameters", "missing 'parameters' object"))
        return problems
    if parameters.get("type") != "object":
        problems.append(Problem(f"{path}.function.parameters.type", "must be 'object'"))

    properties = parameters.get("properties")
    if not isinstance(properties, dict):
        problems.append(Problem(f"{path}.function.parameters.properties", "must be an object"))
        return problems

    for property_name, schema in properties.items():
        problems.extend(
            _check_property(property_name, schema, f"{path}.function.parameters.properties.{property_name}")
        )

    required = parameters.get("required", [])
    if not isinstance(required, list):
        problems.append(Problem(f"{path}.function.parameters.required", "must be a list"))
    else:
        for entry in required:
            if entry not in properties:
                problems.append(
                    Problem(f"{path}.function.parameters.required", f"{entry!r} is not a declared property")
                )
    return problems


def validate_document(payload: object, path: str = "document") -> list[Problem]:
    if isinstance(payload, dict) and isinstance(payload.get("tools"), list):
        problems: list[Problem] = []
        for index, tool in enumerate(payload["tools"]):
            problems.extend(validate_tool(tool, f"{path}.tools[{index}]"))
        if not payload["tools"]:
            problems.append(Problem(f"{path}.tools", "no tools to validate"))
        return problems
    if isinstance(payload, dict) and "function" in payload:
        return validate_tool(payload, path)
    return [Problem(path, "expected {'tools': [...]} or a single tool object")]
