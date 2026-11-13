"""Hand-built AST helpers (spans are synthetic, unique per node via a counter)."""

from __future__ import annotations

from itertools import count

from sipl import ast
from sipl.spans import SourceSpan

_c = count(0)


def sp() -> SourceSpan:
    n = next(_c)
    return SourceSpan(n, n + 1, 1, n + 1, 1, n + 2)


def num(v: int) -> ast.Num:
    return ast.Num(sp(), v)


def var(n: str) -> ast.Var:
    return ast.Var(sp(), n)


def binop(op: str, l: ast.Aexp, r: ast.Aexp) -> ast.BinOp:
    return ast.BinOp(sp(), op, l, r)


def parena(a: ast.Aexp) -> ast.ParenA:
    return ast.ParenA(sp(), a)


def eq(l: ast.Aexp, r: ast.Aexp) -> ast.Cmp:
    return ast.Cmp(sp(), "=", l, r)


def gt(l: ast.Aexp, r: ast.Aexp) -> ast.Cmp:
    return ast.Cmp(sp(), ">", l, r)


def or_(l: ast.Bexp, r: ast.Bexp) -> ast.Or:
    return ast.Or(sp(), l, r)


def not_(b: ast.Bexp) -> ast.Not:
    return ast.Not(sp(), b)


def parenb(b: ast.Bexp) -> ast.ParenB:
    return ast.ParenB(sp(), b)


def assign(t: str, v: ast.Aexp | int) -> ast.Assign:
    return ast.Assign(sp(), t, sp(), num(v) if isinstance(v, int) else v)


def seq(*items: ast.Stm) -> ast.Stm:
    return items[0] if len(items) == 1 else ast.Seq(sp(), tuple(items))


def if_(c: ast.Bexp, t: ast.Stm, e: ast.Stm) -> ast.If:
    return ast.If(sp(), c, t, e)


def while_(c: ast.Bexp, b: ast.Stm) -> ast.While:
    return ast.While(sp(), c, b)


def block(b: ast.Stm) -> ast.Block:
    return ast.Block(sp(), b)


def skip() -> ast.Skip:
    return ast.Skip(sp())


def prog(body: ast.Stm) -> ast.Program:
    return ast.Program(sp(), body)
