"""Parser tests: AST shape, precedence, spans, API."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from sipl import ast
from sipl.errors import SiplSyntaxError
from sipl.parser import check, parse, parse_aexp, parse_bexp

CORPUS = Path(__file__).parent / "grammar"
POWER = "begin R := 1; while Y > 0 do begin R := R * X; Y := Y - 1 end end"


def body(src: str) -> Any:
    return parse(src).body


def sexp(n: Any) -> str:
    """Compact rendering ignoring spans, for shape assertions."""
    if isinstance(n, ast.Num):
        return str(n.value)
    if isinstance(n, ast.Var):
        return n.name
    if isinstance(n, ast.BinOp):
        return f"({sexp(n.left)} {n.op} {sexp(n.right)})"
    if isinstance(n, ast.ParenA):
        return f"[{sexp(n.inner)}]"
    if isinstance(n, ast.Cmp):
        return f"({sexp(n.left)} {n.op} {sexp(n.right)})"
    if isinstance(n, ast.Or):
        return f"(or {sexp(n.left)} {sexp(n.right)})"
    if isinstance(n, ast.Not):
        return f"(not {sexp(n.operand)})"
    if isinstance(n, ast.ParenB):
        return f"[{sexp(n.inner)}]"
    raise AssertionError(n)


# ---- precedence / associativity ----


@pytest.mark.parametrize(
    ("src", "shape"),
    [
        ("1 + 2 * 3", "(1 + (2 * 3))"),
        ("1 * 2 + 3", "((1 * 2) + 3)"),
        ("1 - 2 - 3", "((1 - 2) - 3)"),
        ("1 + 2 - 3 + 4", "(((1 + 2) - 3) + 4)"),
        ("2 * 3 * 4", "((2 * 3) * 4)"),
        ("(1 + 2) * 3", "([(1 + 2)] * 3)"),
        ("a - 1", "(a - 1)"),
        ("a -1", "(a - 1)"),
        ("a-1", "(a - 1)"),
        ("a - -1", "(a - -1)"),
        ("-1", "-1"),
        ("- 7", "-7"),
        ("3 * -2", "(3 * -2)"),
        ("(-4)", "[-4]"),
    ],
)
def test_aexp_shape(src: str, shape: str) -> None:
    assert sexp(parse_aexp(src)) == shape


@pytest.mark.parametrize(
    ("src", "shape"),
    [
        ("a = 1 or b > 2", "(or (a = 1) (b > 2))"),
        ("a = 1 ∨ b > 2", "(or (a = 1) (b > 2))"),
        ("not a = 1 or b = 2", "(or (not (a = 1)) (b = 2))"),
        ("¬ a = 1 ∨ b = 2", "(or (not (a = 1)) (b = 2))"),
        ("a = 1 or b = 2 or c = 3", "(or (or (a = 1) (b = 2)) (c = 3))"),
        ("not not a > 1", "(not (not (a > 1)))"),
        ("not (a = 1 or b = 2)", "(not [(or (a = 1) (b = 2))])"),
        ("(a) > 1", "([a] > 1)"),
        ("(a = 1)", "[(a = 1)]"),
        ("((a + 1)) = 2 * 3", "([[(a + 1)]] = (2 * 3))"),
        ("a + 1 > b * 2", "((a + 1) > (b * 2))"),
    ],
)
def test_bexp_shape(src: str, shape: str) -> None:
    assert sexp(parse_bexp(src)) == shape


def test_unicode_and_ascii_equivalent() -> None:
    a = parse("begin if ¬(x = 1) ∨ x > 5 then skip else skip end")
    b = parse("begin if not(x = 1) or x > 5 then skip else skip end")
    assert sexp(a.body.cond) == sexp(b.body.cond)  # type: ignore[attr-defined]


def test_negative_literal_values() -> None:
    p = parse("begin x := -5; y := x -1; z := x - 1 end")
    x, y, z = p.body.items  # type: ignore[attr-defined]
    assert x.value == ast.Num(x.value.span, -5)
    assert isinstance(y.value, ast.BinOp) and y.value.right.value == 1
    assert isinstance(z.value, ast.BinOp) and z.value.op == "-"


def test_keywords_prefixes_are_names() -> None:
    p = parse("begin begin_x := endx; ifx := 1 end")
    assert [s.target for s in p.body.items] == ["begin_x", "ifx"]  # type: ignore[attr-defined]


# ---- statements ----


def test_seq_flattened() -> None:
    b = body("begin a := 1; b := 2; c := 3; d := 4 end")
    assert isinstance(b, ast.Seq)
    assert len(b.items) == 4
    assert all(isinstance(i, ast.Assign) for i in b.items)


def test_single_statement_not_wrapped() -> None:
    assert isinstance(body("begin skip end"), ast.Skip)
    assert isinstance(body("begin x := 1 end"), ast.Assign)


def test_nested_block_is_not_flattened() -> None:
    b = body("begin a := 1; begin b := 2; c := 3 end; d := 4 end")
    assert isinstance(b, ast.Seq) and len(b.items) == 3
    inner = b.items[1]
    assert isinstance(inner, ast.Block)
    assert isinstance(inner.body, ast.Seq) and len(inner.body.items) == 2


def test_if_while_bodies_are_single_statements() -> None:
    b = body("begin if x > 0 then a := 1 else b := 2; c := 3 end")
    assert isinstance(b, ast.Seq) and isinstance(b.items[0], ast.If)
    b = body("begin while x > 0 do x := x - 1; y := 1 end")
    assert isinstance(b, ast.Seq) and isinstance(b.items[0], ast.While)


def test_dangling_else_binds_inner() -> None:
    b = body("begin if a > 0 then if b > 0 then skip else skip else skip end")
    assert isinstance(b, ast.If) and isinstance(b.then, ast.If)
    assert isinstance(b.orelse, ast.Skip)


# ---- spans ----


def test_power_program_spans() -> None:
    p = parse(POWER)
    s = p.span
    assert (s.start, s.end, s.line, s.col, s.end_line, s.end_col) == (0, len(POWER), 1, 1, 1, 66)
    seq = p.body
    assert isinstance(seq, ast.Seq)
    assert (seq.span.start, seq.span.col, seq.span.end) == (6, 7, 61)
    first, loop = seq.items
    assert isinstance(first, ast.Assign) and isinstance(loop, ast.While)
    assert first.target == "R"
    assert (first.target_span.start, first.target_span.end) == (6, 7)
    assert POWER[first.span.start : first.span.end] == "R := 1"
    assert POWER[loop.span.start : loop.span.end].endswith("end")
    assert POWER[loop.cond.span.start : loop.cond.span.end] == "Y > 0"
    assert isinstance(loop.body, ast.Block)
    blk = POWER[loop.body.span.start : loop.body.span.end]
    assert blk == "begin R := R * X; Y := Y - 1 end"


MULTI = """\
# power
begin
  R := 1;
  while (Y > 0) do
    begin
      R := R * (X + 1);
      Y := Y - 1
    end
end
"""


def test_multiline_spans() -> None:
    p = parse(MULTI)
    assert (p.span.line, p.span.col, p.span.end_line, p.span.end_col) == (2, 1, 9, 4)
    seq = p.body
    assert isinstance(seq, ast.Seq)
    assert (seq.span.line, seq.span.col) == (3, 3)
    assert (seq.span.end_line, seq.span.end_col) == (8, 8)
    a, w = seq.items
    assert isinstance(a, ast.Assign) and isinstance(w, ast.While)
    assert (a.span.line, a.span.col, a.span.end_line, a.span.end_col) == (3, 3, 3, 9)
    assert (a.target_span.line, a.target_span.col, a.target_span.end_col) == (3, 3, 4)
    assert (w.span.line, w.span.col, w.span.end_line, w.span.end_col) == (4, 3, 8, 8)
    assert isinstance(w.cond, ast.ParenB)
    assert (w.cond.span.line, w.cond.span.col, w.cond.span.end_col) == (4, 9, 16)
    assert (w.cond.inner.span.col, w.cond.inner.span.end_col) == (10, 15)
    blk = w.body
    assert isinstance(blk, ast.Block)
    assert (blk.span.line, blk.span.col, blk.span.end_line, blk.span.end_col) == (5, 5, 8, 8)
    inner = blk.body
    assert isinstance(inner, ast.Seq)
    r, y = inner.items
    assert (r.span.line, r.span.col) == (6, 7)
    assert (y.span.line, y.span.col, y.span.end_col) == (7, 7, 17)
    assert isinstance(r, ast.Assign) and isinstance(r.value, ast.BinOp)
    rhs = r.value.right
    assert isinstance(rhs, ast.ParenA)
    assert (rhs.span.col, rhs.span.end_col) == (16, 23)
    src = MULTI
    assert src[rhs.span.start : rhs.span.end] == "(X + 1)"
    assert src[r.value.span.start : r.value.span.end] == "R * (X + 1)"


def test_span_offsets_slice_source() -> None:
    src = "begin\n  if x > 0 then y := -3 else skip\nend"
    p = parse(src)
    iff = p.body
    assert isinstance(iff, ast.If)
    assert src[iff.span.start : iff.span.end] == "if x > 0 then y := -3 else skip"
    assert isinstance(iff.then, ast.Assign)
    assert src[iff.then.value.span.start : iff.then.value.span.end] == "-3"
    assert src[iff.orelse.span.start : iff.orelse.span.end] == "skip"


def test_not_and_or_spans() -> None:
    b = parse_bexp("not (a = 1) or b = 2")
    assert isinstance(b, ast.Or) and isinstance(b.left, ast.Not)
    assert (b.span.start, b.span.end) == (0, 20)
    assert (b.left.span.start, b.left.span.end) == (0, 11)


# ---- AST purity ----


def walk(n: Any) -> Any:
    yield n
    if dataclasses.is_dataclass(n):
        for f in dataclasses.fields(n):
            yield from walk(getattr(n, f.name))
    elif isinstance(n, tuple):
        for x in n:
            yield from walk(x)


ALLOWED = (ast.Node, str, int, tuple)


def corpus_valid() -> list[Path]:
    return sorted((CORPUS / "valid").glob("*.sipl"))


@pytest.mark.parametrize("path", corpus_valid(), ids=lambda p: p.stem)
def test_only_sipl_ast_types(path: Path) -> None:
    from sipl.spans import SourceSpan

    root = parse(path.read_text(encoding="utf-8"))
    for n in walk(root):
        assert isinstance(n, (*ALLOWED, SourceSpan)), type(n)
        assert type(n).__module__ in {"sipl.ast", "sipl.spans", "builtins"}
    for n in walk(root):
        if isinstance(n, ast.Seq):
            assert len(n.items) >= 2


# ---- API ----


def test_parse_aexp_bexp_reject_trailing_input() -> None:
    with pytest.raises(SiplSyntaxError):
        parse_aexp("1 + 2 3")
    with pytest.raises(SiplSyntaxError):
        parse_aexp("x > 1")
    with pytest.raises(SiplSyntaxError):
        parse_bexp("x + 1")
    with pytest.raises(SiplSyntaxError):
        parse_aexp("")


def test_aexp_error_position() -> None:
    (d,) = _diags(lambda: parse_aexp("1 +\n  * 2"))
    assert d.span is not None and (d.span.line, d.span.col) == (2, 3)


def _diags(fn: Any) -> Any:
    with pytest.raises(SiplSyntaxError) as info:
        fn()
    return info.value.diagnostics


def test_check_valid_and_invalid() -> None:
    assert check(POWER) == []
    assert len(check("begin")) == 1


def test_eof_and_empty_input() -> None:
    (d,) = check("")
    assert d.code == "unexpected-eof" and d.expected == ("'begin'",)
    assert d.span is not None and (d.span.line, d.span.col) == (1, 1)


def test_unexpected_character_span() -> None:
    (d,) = check("begin\n x := 1 @\nend")
    assert d.code == "unexpected-character"
    assert d.span is not None
    assert (d.span.line, d.span.col, d.span.end_col, d.span.end - d.span.start) == (2, 9, 10, 1)
    assert "'@'" in d.message


def test_keyword_cannot_be_variable() -> None:
    for kw in ["begin", "end", "if", "then", "else", "while", "do", "skip", "or", "not"]:
        assert check(f"begin skip; {kw} := 1 end"), kw
