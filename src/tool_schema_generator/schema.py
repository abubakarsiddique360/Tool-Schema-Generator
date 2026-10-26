"""Build JSON tool schemas from described functions."""

from __future__ import annotations

import ast

from tool_schema_generator.introspect import FunctionSpec, Parameter

BASE_TYPES = {
    "str": "string",
    "string": "string",
    "Path": "string",
    "datetime": "string",
    "date": "string",
    "UUID": "string",
    "int": "integer",
    "float": "number",
    "Decimal": "number",
    "bool": "boolean",
    "dict": "object",
    "Any": "string",
}
NULL_NAMES = frozenset({"None", "NoneType", "null"})
ARRAY_HEADS = frozenset({"list", "List", "Sequence", "Iterable", "tuple", "Tuple", "set", "Set", "frozenset"})
OBJECT_HEADS = frozenset({"dict", "Dict", "Mapping", "DefaultDict", "MutableMapping"})


def _split_generic(text: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    current: list[str] = []
    for character in text:
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
        if character == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue
        current.append(character)
    if current:
        parts.append("".join(current).strip())
    return [part for part in parts if part]


def _literal_values(text: str) -> list:
    values: list = []
    for part in _split_generic(text):
        try:
            values.append(ast.literal_eval(part))
        except (ValueError, SyntaxError):
            continue
    return values


def _json_type(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "string"


def _with_null(schema: dict) -> dict:
    merged = dict(schema)
    declared = merged.get("type", "string")
    types = [declared] if isinstance(declared, str) else list(declared)
    if "null" not in types:
        types.append("null")
    merged["type"] = types
    return merged


def schema_for(annotation: str) -> dict:
    """Map a source level annotation such as `list[dict[str, int]] | None` to JSON Schema."""
    raw = annotation.strip()
    if not raw:
        return {"type": "string"}
    if raw in NULL_NAMES:
        return {"type": "null"}

    parts = [part.strip() for part in raw.split("|")]
    if len(parts) > 1:
        schemas = [schema_for(part) for part in parts if part not in NULL_NAMES]
        if not schemas:
            return {"type": "null"}
        base = dict(schemas[0])
        declared = base.get("type", "string")
        types = [declared] if isinstance(declared, str) else list(declared)
        for extra in schemas[1:]:
            other = extra.get("type", "string")
            for name in [other] if isinstance(other, str) else list(other):
                if name not in types:
                    types.append(name)
        if any(part in NULL_NAMES for part in parts):
            types.append("null")
        base["type"] = types if len(types) > 1 else types[0]
        return base

    if "[" in raw and raw.endswith("]"):
        head, _, inner = raw.partition("[")
        inner = inner[:-1]
        head = head.split(".")[-1]
        if head in ARRAY_HEADS:
            element = _split_generic(inner)
            return {"type": "array", "items": schema_for(element[0]) if element else {"type": "string"}}
        if head in OBJECT_HEADS:
            pair = _split_generic(inner)
            value = pair[1] if len(pair) > 1 else ""
            return {"type": "object", "additionalProperties": schema_for(value) if value else {"type": "string"}}
        if head == "Optional":
            return _with_null(schema_for(inner))
        if head == "Literal":
            values = _literal_values(inner)
            if values:
                return {"enum": values, "type": _json_type(values[0])}
            return {"type": "string"}

    return {"type": BASE_TYPES.get(raw.split(".")[-1], "string")}


def _literal_default(text: str):
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return text


def parameter_schema(parameter: Parameter) -> dict:
    if parameter.kind in {"var_positional", "var_keyword"}:
        schema = {"type": "array", "items": schema_for(parameter.annotation)}
    else:
        schema = schema_for(parameter.annotation)
    if parameter.description:
        schema["description"] = parameter.description
    if parameter.default is not None and not parameter.required:
        schema["default"] = _literal_default(parameter.default)
    return schema


def function_schema(spec: FunctionSpec) -> dict:
    properties = {parameter.name: parameter_schema(parameter) for parameter in spec.parameters}
    required = [parameter.name for parameter in spec.parameters if parameter.required]
    parameters: dict = {"type": "object", "properties": properties}
    if required:
        parameters["required"] = required
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": parameters,
        },
    }


def module_schema(specs: list[FunctionSpec]) -> dict:
    return {"tools": [function_schema(spec) for spec in specs]}
