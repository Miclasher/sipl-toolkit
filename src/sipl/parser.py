"""SIPL parser: Lark LALR grammar -> typed ``sipl.ast`` nodes with exact source spans."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from lark import Lark, Token, Transformer
from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedEOF,
    UnexpectedInput,
    UnexpectedToken,
    VisitError,
)

from . import ast
from .errors import Diagnostic, SiplSyntaxError
from .spans import SourceSpan

__all__ = ["check", "parse", "parse_aexp", "parse_bexp"]


def _grammar_path() -> Path:
    installed = Path(__file__).resolve().parent / "sipl.lark"
    if installed.is_file():
        return installed
    return Path(__file__).resolve().parents[2] / "grammar" / "sipl.lark"


@lru_cache(maxsize=1)
def _lark() -> Lark:
    return Lark(
        _grammar_path().read_text(encoding="utf-8"),
        parser="lalr",
        start=["program", "aexp", "bexp"],
        keep_all_tokens=True,
        maybe_placeholders=False,
    )


# ---------------------------------------------------------------- spans


def _span(first: Token | ast.Node, last: Token | ast.Node | None = None) -> SourceSpan:
    last = first if last is None else last
    if isinstance(first, Token):
        s_start, s_line, s_col = first.start_pos or 0, first.line or 1, first.column or 1
    else:
        s_start, s_line, s_col = first.span.start, first.span.line, first.span.col
    if isinstance(last, Token):
        e_end, e_line, e_col = last.end_pos or 0, last.end_line or 1, last.end_column or 1
    else:
        e_end, e_line, e_col = last.span.end, last.span.end_line, last.span.end_col
    return SourceSpan(s_start, e_end, s_line, s_col, e_line, e_col)


class _Builder(Transformer[Token, Any]):
    """Builds our AST. Children include all tokens (keep_all_tokens=True)."""

    def program(self, c: list[Any]) -> ast.Program:
        return ast.Program(_span(c[0], c[2]), c[1])

    def seq(self, c: list[Any]) -> ast.Seq:
        items = tuple(c[::2])
        return ast.Seq(_span(items[0], items[-1]), items)

    def assign(self, c: list[Any]) -> ast.Assign:
        return ast.Assign(_span(c[0], c[2]), str(c[0]), _span(c[0]), c[2])

    def ifstmt(self, c: list[Any]) -> ast.If:
        return ast.If(_span(c[0], c[5]), c[1], c[3], c[5])

    def whilestmt(self, c: list[Any]) -> ast.While:
        return ast.While(_span(c[0], c[3]), c[1], c[3])

    def block(self, c: list[Any]) -> ast.Block:
        return ast.Block(_span(c[0], c[2]), c[1])

    def skip(self, c: list[Any]) -> ast.Skip:
        return ast.Skip(_span(c[0]))

    def _bin(self, c: list[Any]) -> ast.BinOp:
        return ast.BinOp(_span(c[0], c[2]), str(c[1]), c[0], c[2])

    add = sub = mul = _bin

    def num(self, c: list[Any]) -> ast.Num:
        return ast.Num(_span(c[0]), int(c[0]))

    def neg(self, c: list[Any]) -> ast.Num:
        return ast.Num(_span(c[0], c[1]), -int(c[1]))

    def var(self, c: list[Any]) -> ast.Var:
        return ast.Var(_span(c[0]), str(c[0]))

    def parena(self, c: list[Any]) -> ast.ParenA:
        return ast.ParenA(_span(c[0], c[2]), c[1])

    def _cmp(self, c: list[Any]) -> ast.Cmp:
        return ast.Cmp(_span(c[0], c[2]), str(c[1]), c[0], c[2])

    eq = gt = _cmp

    def or_(self, c: list[Any]) -> ast.Or:
        return ast.Or(_span(c[0], c[2]), c[0], c[2])

    def not_(self, c: list[Any]) -> ast.Not:
        return ast.Not(_span(c[0], c[1]), c[1])

    def parenb(self, c: list[Any]) -> ast.ParenB:
        return ast.ParenB(_span(c[0], c[2]), c[1])


# ---------------------------------------------------------------- diagnostics

_TERMINAL_NAMES = {
    "BEGIN": "'begin'",
    "END": "'end'",
    "IF": "'if'",
    "THEN": "'then'",
    "ELSE": "'else'",
    "WHILE": "'while'",
    "DO": "'do'",
    "SKIP": "'skip'",
    "OR": "'or'",
    "NOT": "'not'",
    "NAME": "identifier",
    "INT": "number",
    "ASSIGN": "':='",
    "SEMI": "';'",
    "PLUS": "'+'",
    "MINUS": "'-'",
    "STAR": "'*'",
    "EQ": "'='",
    "GT": "'>'",
    "LPAR": "'('",
    "RPAR": "')'",
    "$END": "end of input",
}


def _display(terminals: Any) -> tuple[str, ...]:
    names = [_TERMINAL_NAMES.get(t, str(t)) for t in terminals]
    order = {n: i for i, n in enumerate(_TERMINAL_NAMES.values())}
    return tuple(sorted(set(names), key=lambda n: (order.get(n, 999), n)))


def _expected_suffix(expected: tuple[str, ...]) -> str:
    if not expected:
        return ""
    if len(expected) == 1:
        return f", expected {expected[0]}"
    return ", expected one of: " + ", ".join(expected)


def _point(source: str, offset: int) -> SourceSpan:
    """Zero-width span at ``offset``."""
    line = source.count("\n", 0, offset) + 1
    col = offset - (source.rfind("\n", 0, offset) + 1) + 1
    return SourceSpan(offset, offset, line, col, line, col)


def _diagnostic(source: str, exc: UnexpectedInput) -> Diagnostic:
    if isinstance(exc, UnexpectedToken):
        tok = exc.token
        terminals = getattr(exc, "accepts", None) or exc.expected or ()
        expected = _display(terminals)
        if tok.type == "$END":
            return Diagnostic(
                "unexpected-eof",
                "unexpected end of input" + _expected_suffix(expected),
                _point(source, len(source)),
                expected=expected,
            )
        return Diagnostic(
            "unexpected-token",
            f"unexpected '{tok.value}'" + _expected_suffix(expected),
            _span(tok),
            expected=expected,
        )
    if isinstance(exc, UnexpectedCharacters):
        pos = exc.pos_in_stream or 0
        ch = source[pos]
        expected = _display(exc.allowed or ())
        span = SourceSpan(pos, pos + 1, exc.line, exc.column, exc.line, exc.column + 1)
        return Diagnostic(
            "unexpected-character",
            f"unexpected character {ch!r}" + _expected_suffix(expected),
            span,
            expected=expected,
        )
    if isinstance(exc, UnexpectedEOF):
        expected = _display(exc.expected)
        return Diagnostic(
            "unexpected-eof",
            "unexpected end of input" + _expected_suffix(expected),
            _point(source, len(source)),
            expected=expected,
        )
    return Diagnostic("syntax-error", str(exc), None)


def _too_deep() -> Diagnostic:
    return Diagnostic(
        "nesting-too-deep", "expression or block nesting is too deep for the parser", None
    )


def _run(source: str, start: str) -> Any:
    try:
        tree = _lark().parse(source, start=start)
        return _Builder().transform(tree)
    except UnexpectedInput as exc:
        raise SiplSyntaxError([_diagnostic(source, exc)]) from None
    except RecursionError:
        raise SiplSyntaxError([_too_deep()]) from None
    except VisitError as exc:
        if isinstance(exc.orig_exc, RecursionError):
            raise SiplSyntaxError([_too_deep()]) from None
        raise SiplSyntaxError([Diagnostic("syntax-error", str(exc.orig_exc), None)]) from None


# ---------------------------------------------------------------- public API


def parse(source: str) -> ast.Program:
    """Parse a whole SIPL program. Raises ``SiplSyntaxError``."""
    result: ast.Program = _run(source, "program")
    return result


def parse_aexp(source: str) -> ast.Aexp:
    """Parse ``source`` as a single arithmetic expression."""
    result: ast.Aexp = _run(source, "aexp")
    return result


def parse_bexp(source: str) -> ast.Bexp:
    """Parse ``source`` as a single condition."""
    result: ast.Bexp = _run(source, "bexp")
    return result


def check(source: str) -> list[Diagnostic]:
    """Return syntax diagnostics for a program (empty when valid)."""
    try:
        parse(source)
    except SiplSyntaxError as exc:
        return list(exc.diagnostics)
    return []
