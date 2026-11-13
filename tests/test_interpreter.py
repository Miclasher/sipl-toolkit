import pytest

from helpers_ast import (
    assign,
    binop,
    block,
    eq,
    gt,
    if_,
    not_,
    num,
    or_,
    parena,
    parenb,
    prog,
    seq,
    skip,
    var,
    while_,
)
from sipl.interpreter import UndefinedVariable, eval_aexp, eval_bexp, run


def power():
    # R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end
    return prog(
        seq(
            assign("R", 1),
            while_(
                gt(var("Y"), num(0)),
                block(
                    seq(
                        assign("R", binop("*", var("R"), var("X"))),
                        assign("Y", binop("-", var("Y"), num(1))),
                    )
                ),
            ),
        )
    )


def test_power():
    r = run(power(), {"X": 5, "Y": 2})
    assert r.status == "ok" and r.error is None
    assert r.state == {"X": 5, "Y": 0, "R": 25}
    # R:=1 (1) + while checks: 3 + 2 iterations * 2 assigns = 1 + 3 + 4 -> While counts 3 checks
    assert r.steps == 1 + 3 + 4
    assert r.to_json()["status"] == "ok"


def test_if_branches():
    p = prog(if_(eq(var("X"), num(1)), assign("R", 10), assign("R", 20)))
    assert run(p, {"X": 1}).state["R"] == 10
    assert run(p, {"X": 2}).state["R"] == 20
    assert run(p, {"X": 2}).steps == 2


def test_skip_and_blocks():
    r = run(prog(block(block(seq(skip(), assign("A", 3))))), {})
    assert r.state == {"A": 3} and r.steps == 2


def test_zero_iterations():
    r = run(prog(while_(gt(num(0), num(1)), assign("A", 1))))
    assert r.state == {} and r.steps == 1


def test_undefined_variable():
    z = var("Z")
    r = run(prog(seq(assign("A", 1), assign("B", binop("+", var("A"), z)))))
    assert r.status == "error" and r.error is not None
    assert r.error.code == "undefined-variable"
    assert r.error.span == z.span
    assert "'Z'" in r.error.message
    assert r.state == {"A": 1} and r.steps == 2
    assert r.to_json()["error"]["code"] == "undefined-variable"


def test_or_not_evaluates_both():
    q = var("Q")
    with pytest.raises(UndefinedVariable) as ei:
        eval_bexp(or_(eq(num(1), num(1)), eq(q, num(0))), {})
    assert ei.value.name == "Q" and ei.value.span == q.span


def test_or_not_paren():
    st = {"X": 3}
    b = or_(gt(var("X"), num(5)), not_(parenb(eq(var("X"), num(4)))))
    assert eval_bexp(b, st) is True
    assert eval_bexp(not_(b), st) is False
    assert eval_aexp(parena(binop("-", num(2), num(7))), st) == -5


def test_negative_and_bigint():
    assert run(prog(assign("A", binop("-", num(0), num(5))))).state == {"A": -5}
    p = prog(
        seq(
            assign("A", 1),
            assign("I", 200),
            while_(
                gt(var("I"), num(0)),
                seq(
                    assign("A", binop("*", var("A"), num(2))),
                    assign("I", binop("-", var("I"), num(1))),
                ),
            ),
        )
    )
    assert run(p).state["A"] == 2**200


def test_step_limit():
    r = run(prog(while_(eq(num(1), num(1)), skip())), max_steps=50)
    assert r.status == "error" and r.error is not None
    assert r.error.code == "step-limit-exceeded" and "50" in r.error.message
    assert r.steps == 50
    r2 = run(prog(while_(eq(num(1), num(1)), skip())))
    assert r2.error is not None and r2.steps == 100_000


def test_step_limit_on_statement():
    r = run(prog(seq(skip(), skip(), skip())), max_steps=2)
    assert r.error is not None and r.error.code == "step-limit-exceeded"
    assert run(prog(seq(skip(), skip())), max_steps=2).status == "ok"


def test_deep_seq():
    items = [assign("A", binop("+", var("A"), num(1))) for _ in range(5000)]
    r = run(prog(seq(assign("A", 0), *items)))
    assert r.state["A"] == 5000


def test_deep_blocks():
    node = assign("A", 7)
    for _ in range(1000):
        node = block(node)
    assert run(prog(node)).state == {"A": 7}


def test_deep_if():
    node = assign("A", 7)
    for _ in range(1000):
        node = if_(eq(num(1), num(1)), node, skip())
    assert run(prog(node)).state == {"A": 7}


def test_initial_not_mutated():
    init = {"X": 1}
    run(prog(assign("X", 2)), init)
    assert init == {"X": 1}
