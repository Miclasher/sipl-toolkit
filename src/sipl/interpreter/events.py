"""Execution events (CORE-04). Every event serializes to JSON via to_json()."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ast import Node
from ..spans import SourceSpan

State = dict[str, int]


@dataclass(frozen=True)
class Event:
    kind: str = ""

    def to_json(self) -> dict[str, Any]:  # overridden
        return {"kind": self.kind}


@dataclass(frozen=True)
class ProgramStarted(Event):
    state: tuple[tuple[str, int], ...] = ()
    kind: str = "program_started"

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind, "state": dict(self.state)}


@dataclass(frozen=True)
class BeforeStatement(Event):
    node: Node | None = None
    span: SourceSpan | None = None
    stmt_type: str = ""  # "Assign" | "If" | "While" | "Skip" ...
    state: tuple[tuple[str, int], ...] = ()
    step: int = 0
    kind: str = "before_statement"

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "stmt": self.stmt_type,
            "span": self.span.to_json() if self.span else None,
            "state": dict(self.state),
            "step": self.step,
        }


@dataclass(frozen=True)
class AfterStatement(Event):
    node: Node | None = None
    span: SourceSpan | None = None
    stmt_type: str = ""
    state: tuple[tuple[str, int], ...] = ()
    step: int = 0
    kind: str = "after_statement"

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "stmt": self.stmt_type,
            "span": self.span.to_json() if self.span else None,
            "state": dict(self.state),
            "step": self.step,
        }


@dataclass(frozen=True)
class VariableChanged(Event):
    name: str = ""
    old: int | None = None  # None = previously undefined
    new: int = 0
    span: SourceSpan | None = None
    kind: str = "variable_changed"

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "old": self.old,
            "new": self.new,
            "span": self.span.to_json() if self.span else None,
        }


@dataclass(frozen=True)
class ConditionEvaluated(Event):
    span: SourceSpan | None = None
    value: bool = False
    owner: str = ""  # "If" | "While"
    kind: str = "condition_evaluated"

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "owner": self.owner,
            "value": self.value,
            "span": self.span.to_json() if self.span else None,
        }


@dataclass(frozen=True)
class ProgramFinished(Event):
    state: tuple[tuple[str, int], ...] = ()
    steps: int = 0
    kind: str = "program_finished"

    def to_json(self) -> dict[str, Any]:
        return {"kind": self.kind, "state": dict(self.state), "steps": self.steps}


@dataclass(frozen=True)
class ExecutionError(Event):
    """Terminal event: runtime error or limit exceeded."""

    code: str = ""  # "undefined-variable" | "step-limit-exceeded"
    message: str = ""
    span: SourceSpan | None = None
    state: tuple[tuple[str, int], ...] = ()
    steps: int = 0
    kind: str = "execution_error"

    def to_json(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "code": self.code,
            "message": self.message,
            "span": self.span.to_json() if self.span else None,
            "state": dict(self.state),
            "steps": self.steps,
        }
