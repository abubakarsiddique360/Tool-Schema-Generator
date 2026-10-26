# Tool-Schema-Generator

[![CI](https://github.com/abubakarsiddique360/Tool-Schema-Generator/actions/workflows/ci.yml/badge.svg)](https://github.com/abubakarsiddique360/Tool-Schema-Generator/actions/workflows/ci.yml)
![python](https://img.shields.io/badge/python-3.10%20%7C%203.12-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![dependencies](https://img.shields.io/badge/dependencies-none-success)

Describe a Python function with a normal docstring, and get the JSON tool schema that function
calling models expect. Then validate the schema before it reaches the model. Standard library only,
no framework, no runtime dependency on any vendor SDK.

## Why it exists

Teaching an agent a new tool usually means hand-writing JSON that repeats what the Python function
already says: the name, the parameters, their types, which ones are optional. Hand-written schemas
drift the moment a signature changes, and a stale schema is worse than no schema, because the model
keeps calling a parameter that no longer exists. `tool-schema` reads the source with `ast`, takes
descriptions from the docstring, and refuses to guess.

## Install

```bash
pip install -e .
```

Python 3.10+, zero runtime dependencies.

## Usage

```bash
tool-schema generate examples/tools.py            # {"tools": [...]} for every public function
tool-schema generate examples/tools.py --single   # a bare list of tools
tool-schema generate examples/tools.py --include-private
tool-schema list examples/tools.py                # required / optional counts per function
tool-schema validate schema.json                  # check a schema file
```

Exit codes: `0` success, `1` the schema has problems, `2` the file cannot be read or parsed.

## Input

```python
def search_docs(query: str, limit: int = 10, *, tags: list[str] | None = None) -> list[str]:
    """Search the documentation index.

    Args:
        query: Words to search for.
        limit: Maximum number of results to return.
        tags: Optional tags to filter the results by.
    """
```

`tool-schema generate` produces:

```json
{
  "type": "function",
  "function": {
    "name": "search_docs",
    "description": "Search the documentation index.",
    "parameters": {
      "type": "object",
      "properties": {
        "query": { "type": "string", "description": "Words to search for." },
        "limit": { "type": "integer", "description": "Maximum number of results to return.", "default": 10 },
        "tags": {
          "type": ["array", "null"],
          "items": { "type": "string" },
          "description": "Optional tags to filter the results by.",
          "default": null
        }
      },
      "required": ["query"]
    }
  }
}
```

Notice the details that usually get lost by hand: `keyword-only` parameters stay optional, `Literal`
becomes an `enum`, `list[str] | None` keeps its item type **and** gains `null`, and the default is
emitted as a real JSON value rather than the source text.

## Type mapping

| Python annotation | JSON Schema |
| --- | --- |
| `str`, `Path`, `datetime`, `date`, `UUID` | `{"type": "string"}` |
| `int` | `{"type": "integer"}` |
| `float`, `Decimal` | `{"type": "number"}` |
| `bool` | `{"type": "boolean"}` |
| `list[X]`, `Sequence[X]`, `set[X]`, `tuple[X, ...]` | `{"type": "array", "items": <X>}` |
| `dict[str, X]`, `Mapping[str, X]` | `{"type": "object", "additionalProperties": <X>}` |
| `Optional[X]`, `X \| None` | `<X>` with `null` added to `type` |
| `Literal["a", "b"]` | `{"type": "string", "enum": ["a", "b"]}` |
| anything else, or no annotation | `{"type": "string"}` |

`*args` and `**kwargs` become arrays and are never marked required.

## Descriptions

The first paragraph of the docstring becomes the tool description. Parameter descriptions are read
from a Google style `Args:` / `Arguments:` / `Parameters:` section (indented continuation lines are
joined), or from Sphinx style `:param name: ...` lines. A `Returns:` section stops parameter
parsing, so prose never leaks into a parameter description.

## Validation

`tool-schema validate` checks a saved schema without needing the source module:

- `type` is `function` and a `function` object exists;
- the name matches `^[A-Za-z0-9_-]{1,64}$`;
- the description is present and at most 1024 characters;
- `parameters.type` is `object` with a `properties` object;
- every `required` entry is a declared property;
- every property declares a known `type` (a string or a list, so `["array", "null"]` passes) or an
  `enum`, and arrays declare `items`.

Problems are reported as `path.to.field: message`, so a machine can point at the exact node.

## Design notes

- **Static, not introspective.** The module is parsed with `ast` and never imported, so generating a
  schema cannot execute the code, import a heavy dependency or trigger a side effect.
- **The docstring is the contract.** Missing descriptions are visible in the output rather than
  invented, which is what makes `tool-schema validate` useful as a CI gate.
- **No clever inference.** Anything unrecognised becomes a string instead of a wrong guess, and the
  mapping table above is the whole story.
- **Schemas are plain dictionaries.** Nothing is coupled to one provider's SDK, so the output can be
  pasted into any function-calling API.
- **Defaults are literal-evaluated**, so `default=10` becomes `10` and `default="celsius"` becomes
  `"celsius"`, not `"'celsius'"`.

## Project layout

```text
src/tool_schema_generator/
  introspect.py  ast scanning, docstring sections, parameter metadata
  schema.py      annotation to JSON Schema mapping, function and module schemas
  validate.py    structural validation with paths
  cli.py         generate / validate / list
examples/
  tools.py       three documented tools plus one private helper
tests/           73 tests across introspection, mapping, validation and the CLI
```

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

CI runs the suite on Python 3.10 and 3.12, checks formatting, then generates a schema from the
example module and validates the file it just produced.

## Limitations

- Only module level `def`/`async def` functions are considered; methods, lambdas and class bodies are
  ignored.
- Annotations must be resolvable at parse time; `typing.Annotated` metadata and string forward
  references are reduced to their base type.
- Union of containers keeps the first schema, so `list[int] | dict[str, int]` loses the object
  branch.
- No `$defs`, `allOf`, `oneOf` or recursion: the output is a flat, strict schema by design.
- Pydantic models, dataclasses and TypedDicts are out of scope.

## License

MIT, copyright (c) 2026 ABU BAKAR SIDDIQUE.
