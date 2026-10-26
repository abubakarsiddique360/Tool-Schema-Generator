from __future__ import annotations

import json
from pathlib import Path

from tool_schema_generator.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
TOOLS = EXAMPLES / "tools.py"


def test_generate(capsys) -> None:
    assert main(["generate", str(TOOLS)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["tools"]) == 3
    assert payload["tools"][0]["function"]["name"] == "get_weather"


def test_generate_single(capsys) -> None:
    assert main(["generate", str(TOOLS), "--single"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert isinstance(payload, list)
    assert len(payload) == 3


def test_generate_includes_private_when_asked(capsys) -> None:
    assert main(["generate", str(TOOLS), "--include-private"]) == 0
    names = [tool["function"]["name"] for tool in json.loads(capsys.readouterr().out)["tools"]]
    assert "_internal_helper" in names


def test_generate_output_is_valid(capsys, tmp_path) -> None:
    main(["generate", str(TOOLS)])
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(capsys.readouterr().out, encoding="utf-8")
    assert main(["validate", str(schema_file)]) == 0
    assert "schema is valid" in capsys.readouterr().out


def test_list(capsys) -> None:
    assert main(["list", str(TOOLS)]) == 0
    out = capsys.readouterr().out
    assert "get_weather" in out
    assert "FUNCTION" in out


def test_missing_module(tmp_path, capsys) -> None:
    assert main(["generate", str(tmp_path / "nope.py")]) == 2
    assert "cannot read" in capsys.readouterr().err


def test_module_without_functions(tmp_path, capsys) -> None:
    path = tmp_path / "empty.py"
    path.write_text("# nothing here\n", encoding="utf-8")
    assert main(["generate", str(path)]) == 2
    assert "no public functions" in capsys.readouterr().err


def test_broken_module(tmp_path, capsys) -> None:
    path = tmp_path / "broken.py"
    path.write_text("def broken(:\n", encoding="utf-8")
    assert main(["generate", str(path)]) == 2
    assert "cannot parse" in capsys.readouterr().err


def test_validate_reports_problems(tmp_path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"tools": [{"type": "nope"}]}), encoding="utf-8")
    assert main(["validate", str(path)]) == 1
    assert "'type' must be 'function'" in capsys.readouterr().out


def test_validate_json_output(tmp_path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"tools": [{"type": "nope"}]}), encoding="utf-8")
    assert main(["validate", str(path), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["problems"][0]["path"].endswith("tools[0]")
    assert payload["problems"][0]["message"] == "'type' must be 'function'"


def test_validate_broken_json(tmp_path, capsys) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{nope}", encoding="utf-8")
    assert main(["validate", str(path)]) == 2
    assert "invalid JSON" in capsys.readouterr().err


def test_validate_tolerates_a_byte_order_mark(tmp_path, capsys) -> None:
    path = tmp_path / "bom.json"
    path.write_bytes(b"\xef\xbb\xbf" + json.dumps({"tools": []}).encode("utf-8"))
    assert main(["validate", str(path)]) == 1
    assert "no tools to validate" in capsys.readouterr().out


def test_validate_missing_file(tmp_path, capsys) -> None:
    assert main(["validate", str(tmp_path / "nope.json")]) == 2
    assert "cannot read" in capsys.readouterr().err
