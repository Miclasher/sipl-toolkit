"""Evaluation of arithmetic (A) and boolean (B) expressions over a state."""

from __future__ import annotations

from collections.abc import Mapping

from .. import ast
from ..spans import SourceSpan


class EvaluationError(Exception):
    """Base for errors that make a semantic function undefined at a state."""

    code = "evaluation-error"

    def __init__(self, message: str, span: SourceSpan) -> None:
        self.span = span
        super().__init__(message)


class UndefinedVariable(EvaluationError):
    code = "undefined-variable"

    def __init__(self, name: str, span: SourceSpan) -> None:
        self.name = name
        super().__init__(f"variable '{name}' is not defined", span)


class DivisionByZero(EvaluationError):
    code = "division-by-zero"

    def __init__(self, span: SourceSpan) -> None:
        super().__init__("division by zero", span)


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
    if a.op == "div":
        if right == 0:
            raise DivisionByZero(a.right.span)
        return left // right  # floor division; equals the usual div on naturals
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
