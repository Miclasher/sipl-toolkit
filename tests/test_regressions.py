"""Regression tests for defects found in the independent review."""

import io
import json

import pytest

from sipl.cli import main
from sipl.dap.protocol import read_message
from sipl.dap.server import serve
from sipl.errors import SiplSyntaxError
from sipl.interpreter import run
from sipl.parser import parse
from test_dap import Client

LOOP = "begin\n n := 3;\n while n > 0 do\n n := n - 1;\n skip\nend\n"


def test_breakpoint_in_single_statement_loop_hits_every_iteration(tmp_path):
    f = tmp_path / "loop.sipl"
    f.write_text(LOOP)
    c = Client()
    c.start(program=str(f), bps=[4], stopOnEntry=False)
    hits = 0
    while c.stopped() and c.stopped()["reason"] == "breakpoint":
        hits += 1
        c.call("continue", threadId=1)
    assert hits == 3 and "terminated" in c.event_names()


def test_breakpoints_set_before_launch_are_kept(tmp_path):
    f = tmp_path / "loop.sipl"
    f.write_text(LOOP)
    c = Client()
    c.call("initialize")
    c.call("setBreakpoints", breakpoints=[{"line": 4}])
    assert c.call("launch", program=str(f), stopOnEntry=False)["success"]
    c.call("configurationDone")
    assert c.stopped()["reason"] == "breakpoint" and c.frame()["line"] == 4


def test_relaunch_after_finish(tmp_path):
    f = tmp_path / "p.sipl"
    f.write_text("begin X := 1 end")
    c = Client()
    c.start(program=str(f))
    c.call("continue", threadId=1)
    assert "terminated" in c.event_names()
    assert c.call("launch", program=str(f))["success"]
    c.call("configurationDone")
    assert (
        c.stopped()["reason"] == "entry" and len(c.call("stackTrace")["body"]["stackFrames"]) == 1
    )


def test_huge_integers_run_and_json(tmp_path, capsys):
    f = tmp_path / "big.sipl"
    f.write_text("begin x := 2; n := 14; while n > 0 do begin x := x * x; n := n - 1 end end")
    assert main(["run", str(f), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["state"]["x"] == 2 ** (2**14)
    assert main(["run", str(f)]) == 0
    big = "9" * 5000
    assert run(parse(f"begin x := {big} end")).state["x"] == int(big)


def test_parser_deep_nesting_is_a_diagnostic():
    with pytest.raises(SiplSyntaxError) as e:
        parse("begin x := " + "1+" * 5000 + "1 end")
    assert e.value.diagnostics[0].code == "nesting-too-deep"
    with pytest.raises(SiplSyntaxError):
        parse("begin " * 5000 + "skip" + " end" * 5000)


def test_cli_invalid_utf8(tmp_path, capsys):
    f = tmp_path / "bad.sipl"
    f.write_bytes(b"begin x := 1; \xff end")
    assert main(["run", str(f)]) == 66
    assert "not valid UTF-8" in capsys.readouterr().err


def test_dap_survives_bad_requests(tmp_path):
    f = tmp_path / "bad.sipl"
    f.write_bytes(b"begin \xff end")
    c = Client()
    c.call("initialize")
    assert not c.call("setBreakpoints", breakpoints=[{"line": "x"}])["success"]
    assert c.call("setBreakpoints", breakpoints=[{"line": None}])["success"]
    assert not c.call("launch", program=str(f))["success"]
    assert c.call("threads")["success"]


def test_dap_protocol_garbage_does_not_crash_server():
    bad = b"Content-Length: abc\r\n\r\nContent-Length: 5\r\n\r\n{nope"
    body = b'{"seq":1,"type":"request","command":"threads"}'
    good = b"Content-Length: %d\r\n\r\n" % len(body) + body
    assert read_message(io.BytesIO(bad)) == {}
    out = io.BytesIO()
    serve(io.BytesIO(bad + good), out)
    assert b'"threads"' in out.getvalue()


def test_run_control_before_launch_and_double_configuration_done():
    c = Client()
    c.call("initialize")
    for cmd in ("continue", "next", "stepIn", "stepOut"):
        assert not c.call(cmd, threadId=1)["success"]
    assert not c.call("evaluate", expression="1")["success"]
    c.start(program=str(__import__("test_dap").POWER))
    assert not c.call("configurationDone")["success"]


# ---- `div` extension ----
def _run_src(src, **init):
    return run(parse(src), init)


def test_div_precedence_and_associativity():
    assert _run_src("begin x := 20 div 3 * 2 end").state["x"] == 12  # (20 div 3) * 2
    assert _run_src("begin x := 1 + 7 div 2 end").state["x"] == 4
    assert _run_src("begin x := 100 div 5 div 2 end").state["x"] == 10
    assert _run_src("begin x := 7 - 7 div 7 end").state["x"] == 6


def test_div_ast_and_spans():
    prog = parse("begin x := a div 2 end")
    expr = prog.body.value
    assert expr.op == "div" and (expr.span.col, expr.span.end_col) == (12, 19)


def test_div_by_zero_is_runtime_error():
    r = _run_src("begin x := 1 div y end", y=0)
    assert r.status == "error" and r.error.code == "division-by-zero"
    assert r.error.span.col == 18  # points at the divisor


def test_div_floor_semantics_for_negatives():
    assert _run_src("begin x := -7 div 2 end").state["x"] == -4


def test_identifiers_starting_with_div_still_valid():
    r = _run_src("begin divisor := 6; q := divisor div 2; div2 := q end")
    assert r.state == {"divisor": 6, "q": 3, "div2": 3}


def test_div_is_reserved():
    with pytest.raises(SiplSyntaxError):
        parse("begin div := 1 end")


def test_div_in_debugger_evaluate_and_cli(capsys):
    c = Client()
    c.start(inputs={"X": 7, "Y": 0})
    assert c.call("evaluate", expression="X div 2")["body"]["result"] == "3"
    assert "division by zero" in c.call("evaluate", expression="X div Y")["message"]
