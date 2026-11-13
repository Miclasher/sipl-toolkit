"""Evaluation of arithmetic (A) and boolean (B) expressions over a state."""

from __future__ import annotations

from collections.abc import Mapping

from .. import ast
from ..spans import SourceSpan


class UndefinedVariable(Exception):
    def __init__(self, name: str, span: SourceSpan) -> None:
        self.name = name
        self.span = span
        super().__init__(f"variable '{name}' is not defined")


def eval_aexp(a: ast.Aexp, state: Mapping[str, int]) -> int:
    if isinstance(a, ast.Num):
        return a.value
    if isinstance(a, ast.Var):
        try:
            return state[a.name]
        except KeyError:
            raise UndefinedVariable(a.name, a.span) from None
    if isinstance(a, ast.ParenA):
        return eval_aexp(a.inner, state)
    left = eval_aexp(a.left, state)
    right = eval_aexp(a.right, state)
    if a.op == "+":
        return left + right
    if a.op == "-":
        return left - right
    if a.op == "*":
        return left * right
    raise ValueError(f"unknown arithmetic operator {a.op!r}")


def eval_bexp(b: ast.Bexp, state: Mapping[str, int]) -> bool:
    if isinstance(b, ast.Cmp):
        left = eval_aexp(b.left, state)
        right = eval_aexp(b.right, state)
        if b.op == "=":
            return left == right
        if b.op == ">":
            return left > right
        raise ValueError(f"unknown comparison operator {b.op!r}")
    if isinstance(b, ast.Or):
        left_v = eval_bexp(b.left, state)
        right_v = eval_bexp(b.right, state)  # total evaluation: no short-circuit
        return left_v or right_v
    if isinstance(b, ast.Not):
        return not eval_bexp(b.operand, state)
    return eval_bexp(b.inner, state)
