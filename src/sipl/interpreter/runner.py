"""Lazy, stack-safe executor producing a stream of events."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from .. import ast
from .evaluator import UndefinedVariable, eval_aexp, eval_bexp
from .events import (
    AfterStatement,
    BeforeStatement,
    ConditionEvaluated,
    Event,
    ExecutionError,
    ProgramFinished,
    ProgramStarted,
    VariableChanged,
)
from .state import snapshot

# Frames: ("run", stm) | ("after", node, step) | ("check", while_node, charged)
_Frame = tuple[Any, ...]


def execute(
    program: ast.Program,
    initial: Mapping[str, int] | None = None,
    max_steps: int = 100_000,
) -> Iterator[Event]:
    state: dict[str, int] = dict(initial or {})
    steps = 0
    yield ProgramStarted(state=snapshot(state))

    def limit_error(node: ast.Node) -> ExecutionError:
        return ExecutionError(
            code="step-limit-exceeded",
            message=f"step limit of {max_steps} exceeded",
            span=node.span,
            state=snapshot(state),
            steps=steps,
        )

    stack: list[_Frame] = [("run", program.body)]
    while stack:
        frame = stack.pop()
        tag = frame[0]
        try:
            if tag == "after":
                node = frame[1]
                yield AfterStatement(
                    node=node,
                    span=node.span,
                    stmt_type=type(node).__name__,
                    state=snapshot(state),
                    step=frame[2],
                )
            elif tag == "check":
                node = frame[1]
                if not frame[2]:
                    if steps >= max_steps:
                        yield limit_error(node)
                        return
                    steps += 1
                value = eval_bexp(node.cond, state)
                yield ConditionEvaluated(span=node.cond.span, value=value, owner="While")
                if value:
                    stack.append(("check", node, False))
                    stack.append(("run", node.body))
            else:
                node = frame[1]
                if isinstance(node, ast.Seq):
                    stack.extend(("run", s) for s in reversed(node.items))
                elif isinstance(node, ast.Block):
                    stack.append(("run", node.body))
                elif isinstance(node, (ast.Assign, ast.Skip, ast.If, ast.While)):
                    if steps >= max_steps:
                        yield limit_error(node)
                        return
                    steps += 1
                    step = steps
                    name = type(node).__name__
                    yield BeforeStatement(
                        node=node,
                        span=node.span,
                        stmt_type=name,
                        state=snapshot(state),
                        step=step,
                    )
                    if isinstance(node, ast.Assign):
                        new = eval_aexp(node.value, state)
                        old = state.get(node.target)
                        state[node.target] = new
                        yield VariableChanged(
                            name=node.target, old=old, new=new, span=node.target_span
                        )
                        yield AfterStatement(
                            node=node,
                            span=node.span,
                            stmt_type=name,
                            state=snapshot(state),
                            step=step,
                        )
                    elif isinstance(node, ast.Skip):
                        yield AfterStatement(
                            node=node,
                            span=node.span,
                            stmt_type=name,
                            state=snapshot(state),
                            step=step,
                        )
                    elif isinstance(node, ast.If):
                        value = eval_bexp(node.cond, state)
                        yield ConditionEvaluated(span=node.cond.span, value=value, owner="If")
                        stack.append(("after", node, step))
                        stack.append(("run", node.then if value else node.orelse))
                    else:
                        stack.append(("after", node, step))
                        stack.append(("check", node, True))
                else:  # pragma: no cover
                    raise TypeError(f"unknown statement {node!r}")
        except UndefinedVariable as exc:
            yield ExecutionError(
                code="undefined-variable",
                message=str(exc),
                span=exc.span,
                state=snapshot(state),
                steps=steps,
            )
            return
    yield ProgramFinished(state=snapshot(state), steps=steps)


@dataclass
class RunResult:
    status: str
    state: dict[str, int]
    steps: int
    error: ExecutionError | None = None
    events: list[Event] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "state": dict(self.state),
            "steps": self.steps,
            "error": self.error.to_json() if self.error else None,
        }


def run(
    program: ast.Program,
    initial: Mapping[str, int] | None = None,
    max_steps: int = 100_000,
    collect_events: bool = False,
) -> RunResult:
    events: list[Event] = []
    result = RunResult(status="ok", state=dict(initial or {}), steps=0)
    for ev in execute(program, initial, max_steps):
        if collect_events:
            events.append(ev)
        if isinstance(ev, ProgramFinished):
            result.state, result.steps = dict(ev.state), ev.steps
        elif isinstance(ev, ExecutionError):
            result.status, result.error = "error", ev
            result.state, result.steps = dict(ev.state), ev.steps
    result.events = events
    return result
