import json

from helpers_ast import assign, eq, gt, if_, num, prog, seq, skip, var, while_
from sipl import ast
from sipl.interpreter import execute, run
from sipl.interpreter.events import (
    AfterStatement,
    BeforeStatement,
    ConditionEvaluated,
    ExecutionError,
    ProgramFinished,
    ProgramStarted,
    VariableChanged,
)


def test_exact_sequence():
    a = assign("X", 1)
    i = if_(eq(var("X"), num(1)), skip(), a)
    p = prog(seq(a, i))
    ev = list(execute(p))
    kinds = [type(e) for e in ev]
    assert kinds == [
        ProgramStarted,
        BeforeStatement,
        VariableChanged,
        AfterStatement,
        BeforeStatement,
        ConditionEvaluated,
        BeforeStatement,
        AfterStatement,
        AfterStatement,
        ProgramFinished,
    ]
    assert ev[0].state == ()
    assert ev[1].stmt_type == "Assign" and ev[1].step == 1 and ev[1].state == ()
    assert ev[2].old is None and ev[2].new == 1 and ev[2].span == a.target_span
    assert ev[3].state == (("X", 1),)
    assert ev[4].stmt_type == "If" and ev[4].step == 2
    assert ev[5].value is True and ev[5].owner == "If"
    assert ev[6].stmt_type == "Skip" and ev[6].step == 3
    assert ev[8].stmt_type == "If" and ev[8].step == 2
    assert ev[-1].steps == 3 and ev[-1].state == (("X", 1),)


def test_while_events():
    w = while_(gt(var("X"), num(0)), assign("X", num(0)))
    ev = list(execute(prog(w), {"X": 2}))
    owners = [e for e in ev if isinstance(e, ConditionEvaluated)]
    assert [c.value for c in owners] == [True, False]
    assert sum(isinstance(e, BeforeStatement) and e.stmt_type == "While" for e in ev) == 1
    assert sum(isinstance(e, AfterStatement) and e.stmt_type == "While" for e in ev) == 1
    ch = [e for e in ev if isinstance(e, VariableChanged)]
    assert ch[0].old == 2 and ch[0].new == 0


def test_error_terminal():
    ev = list(execute(prog(assign("A", var("U")))))
    assert isinstance(ev[-1], ExecutionError)
    assert not any(isinstance(e, ProgramFinished) for e in ev)


def test_lazy():
    p = prog(while_(eq(num(1), num(1)), skip()))
    it = execute(p, max_steps=10**12)
    first = [next(it) for _ in range(5)]
    assert isinstance(first[0], ProgramStarted)
    it.close()


def test_json_serializable():
    p = prog(
        seq(
            assign("X", 3), while_(gt(var("X"), num(0)), assign("X", num(0))), assign("Y", var("U"))
        )
    )
    r = run(p, collect_events=True)
    assert r.events
    for e in r.events:
        json.dumps(e.to_json())
    json.dumps(r.to_json())
    ok = run(prog(skip()), collect_events=True)
    json.dumps(ok.to_json())
    assert ok.to_json()["error"] is None
    assert isinstance(ok.events[-1], ProgramFinished)
    assert isinstance(p, ast.Program)
