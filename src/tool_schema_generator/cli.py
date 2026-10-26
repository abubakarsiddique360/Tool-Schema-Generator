"""Command line entry point: generate, validate, list."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tool_schema_generator.introspect import IntrospectionError, describe_functions
from tool_schema_generator.schema import function_schema, module_schema
from tool_schema_generator.validate import validate_document


class InputError(ValueError):
    pass


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc.strerror or exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tool-schema",
        description="Turn documented Python functions into JSON tool schemas.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="print the schema for every public function")
    generate.add_argument("module")
    generate.add_argument("--indent", type=int, default=2)
    generate.add_argument("--include-private", action="store_true")
    generate.add_argument("--single", action="store_true", help="emit a bare list of tools")

    validate = sub.add_parser("validate", help="check a schema file")
    validate.add_argument("file")
    validate.add_argument("--json", action="store_true")

    listing = sub.add_parser("list", help="one line per function")
    listing.add_argument("module")
    listing.add_argument("--include-private", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "validate":
        try:
            payload = json.loads(_read(args.file))
        except InputError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except json.JSONDecodeError as exc:
            print(f"error: invalid JSON: {exc.msg}", file=sys.stderr)
            return 2

        problems = validate_document(payload, path=Path(args.file).name)
        if args.json:
            print(json.dumps({"problems": [problem.as_dict() for problem in problems]}, indent=2))
        elif problems:
            for problem in problems:
                print(problem)
        else:
            print("schema is valid")
        return 1 if problems else 0

    try:
        source = _read(args.module)
        specs = describe_functions(source, include_private=args.include_private)
    except (InputError, IntrospectionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not specs:
        print("error: no public functions with a definition were found", file=sys.stderr)
        return 2

    if args.command == "list":
        print(f"{'FUNCTION':<22}{'REQUIRED':<10}{'OPTIONAL':<10}DESCRIPTION")
        for spec in specs:
            optional = len(spec.parameters) - len(spec.required)
            print(f"{spec.name:<22}{len(spec.required):<10}{optional:<10}{spec.description[:60]}")
        return 0

    payload = [function_schema(spec) for spec in specs] if args.single else module_schema(specs)
    print(json.dumps(payload, indent=args.indent or None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
