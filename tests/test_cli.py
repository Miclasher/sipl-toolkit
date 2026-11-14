import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from sipl.cli import main

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"
SCHEMA = json.loads((ROOT / "src/sipl/schemas/cli-output.schema.json").read_text(encoding="utf-8"))


def run_json(capsys, *argv):
    code = main([*argv, "--json"])
    doc = json.loads(capsys.readouterr().out)
    jsonschema.validate(doc, SCHEMA)
    return code, doc


def test_run_power_text(capsys):
    assert main(["run", str(EX / "power.sipl"), "--var", "X=5", "--var", "Y=2"]) == 0
    assert capsys.readouterr().out.split() == ["R", "=", "25", "X", "=", "5", "Y", "=", "0"]


def test_run_json(capsys):
    code, doc = run_json(capsys, "run", str(EX / "power.sipl"), "-v", "X=5", "-v", "Y=2")
    assert code == 0 and doc["ok"] and doc["state"] == {"R": 25, "X": 5, "Y": 0}
    assert doc["steps"] == 8 and doc["error"] is None


@pytest.mark.parametrize(
    ("name", "vars_", "expected"),
    [
        ("gcd", ["A=48", "B=18"], {"A": 6, "B": 6}),
        ("fibonacci", ["N=10"], {"A": 55}),
        ("sum_arith", ["N=3"], {"S": 12}),
    ],
)
def test_examples_results(capsys, name, vars_, expected):
    argv = ["run", str(EX / f"{name}.sipl")]
    for v in vars_:
        argv += ["-v", v]
    code, doc = run_json(capsys, *argv)
    assert code == 0
    for k, v in expected.items():
        assert doc["state"][k] == v


def test_step_limit_exit_2(capsys):
    code, doc = run_json(capsys, "run", str(EX / "infinite.sipl"), "--max-steps", "100")
    assert code == 2 and not doc["ok"] and doc["error"]["code"] == "step-limit-exceeded"


def test_undefined_variable_exit_2(capsys):
    code, doc = run_json(capsys, "run", str(EX / "invalid/undefined_var.sipl"))
    assert code == 2 and doc["error"]["code"] == "undefined-variable"
    assert doc["error"]["span"]["line"] == 3


def test_syntax_error_exit_1_json(capsys):
    code, doc = run_json(capsys, "check", str(EX / "invalid/missing_end.sipl"))
    assert code == 1 and not doc["ok"]
    assert doc["diagnostics"][0]["span"]["line"] == 6


def test_syntax_error_text(capsys):
    assert main(["check", str(EX / "invalid/missing_else.sipl")]) == 1
    assert "missing_else.sipl:3:1: error:" in capsys.readouterr().err


def test_parse_json_and_text(capsys):
    code, doc = run_json(capsys, "parse", str(EX / "power.sipl"))
    assert code == 0 and doc["ast"]["type"] == "Program"
    assert main(["parse", str(EX / "power.sipl")]) == 0
    assert capsys.readouterr().out.startswith("Program")


def test_trace_json_events(capsys):
    code, doc = run_json(capsys, "trace", str(EX / "power.sipl"), "-v", "X=2", "-v", "Y=1")
    kinds = [e["kind"] for e in doc["events"]]
    assert code == 0 and kinds[0] == "program_started" and kinds[-1] == "program_finished"
    assert "variable_changed" in kinds and "condition_evaluated" in kinds


def test_trace_text(capsys):
    assert main(["trace", str(EX / "power.sipl"), "-v", "X=2", "-v", "Y=1"]) == 0
    out = capsys.readouterr().out
    assert "While" in out and "R: None -> 1" in out


def test_trace_error_text(capsys):
    assert main(["trace", str(EX / "infinite.sipl"), "--max-steps", "5"]) == 2
    assert "ERROR step-limit-exceeded" in capsys.readouterr().out


def test_missing_file(capsys):
    assert main(["run", "/nonexistent.sipl"]) == 66
    code, doc = run_json(capsys, "run", "/nonexistent.sipl")
    assert code == 66 and doc["diagnostics"][0]["code"] == "io-error"


def test_stdin(monkeypatch, capsys):
    import io

    monkeypatch.setattr(sys, "stdin", io.StringIO("begin X := 1 end"))
    assert main(["run", "-"]) == 0
    assert "X = 1" in capsys.readouterr().out


@pytest.mark.parametrize(
    "argv",
    [[], ["bogus"], ["run"], ["run", "f", "--var", "X"], ["run", "f", "--var", "X=a"]],
)
def test_usage_errors(argv, capsys):
    assert main(argv) == 64


def test_max_steps_must_be_positive(capsys):
    assert main(["run", str(EX / "power.sipl"), "--max-steps", "0"]) == 64


def test_version(capsys):
    assert main(["--version"]) == 0


def test_subprocess_entrypoint():
    r = subprocess.run(
        [sys.executable, "-m", "sipl", "run", str(EX / "power.sipl"), "-v", "X=3", "-v", "Y=3"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0 and "R = 27" in r.stdout
