"""Typed AST for SIPL. Every node carries a SourceSpan. Nodes are frozen dataclasses.

Textbook categories: Prog (P), Stm (S), Aexp (a), Bexp (b). Rule names in comments follow
the course BNF (P1, S1-S6, A1-A6, B1-B5).
"""

from __future__ import annotations

from dataclasses import dataclass

from .spans import SourceSpan


@dataclass(frozen=True)
class Node:
    span: SourceSpan


# ---- arithmetic expressions (a) ----
@dataclass(frozen=True)
class Num(Node):  # A1
    value: int


@dataclass(frozen=True)
class Var(Node):  # A2
    name: str


@dataclass(frozen=True)
class BinOp(Node):  # A3 '+', A4 '-', A5 '*', A7 'div' (extension)
    op: str  # "+" | "-" | "*" | "div"
    left: Aexp
    right: Aexp


@dataclass(frozen=True)
class ParenA(Node):  # A6
    inner: Aexp


Aexp = Num | Var | BinOp | ParenA


# ---- conditions (b) ----
@dataclass(frozen=True)
class Cmp(Node):  # B1 '=', B2 '>'
    op: str  # "=" | ">"
    left: Aexp
    right: Aexp


@dataclass(frozen=True)
class Or(Node):  # B3
    left: Bexp
    right: Bexp


@dataclass(frozen=True)
class Not(Node):  # B4
    operand: Bexp


@dataclass(frozen=True)
class ParenB(Node):  # B5
    inner: Bexp


Bexp = Cmp | Or | Not | ParenB


# ---- statements (S) ----
@dataclass(frozen=True)
class Assign(Node):  # S1  x := a
    target: str
    target_span: SourceSpan
    value: Aexp


@dataclass(frozen=True)
class Seq(Node):  # S2  S1 ; S2 ; ...   (flattened, len(items) >= 2)
    items: tuple[Stm, ...]


@dataclass(frozen=True)
class If(Node):  # S3
    cond: Bexp
    then: Stm
    orelse: Stm


@dataclass(frozen=True)
class While(Node):  # S4
    cond: Bexp
    body: Stm


@dataclass(frozen=True)
class Block(Node):  # S5  begin S end
    body: Stm


@dataclass(frozen=True)
class Skip(Node):  # S6
    pass


Stm = Assign | Seq | If | While | Block | Skip


@dataclass(frozen=True)
class Program(Node):  # P1  begin S end
    body: Stm
