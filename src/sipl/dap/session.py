"""Debug session: translates DAP requests into stepping over the interpreter's event stream.

The interpreter (sipl.interpreter.execute) is a lazy generator; the session pulls events from
it and pauses on BeforeStatement events. No threads are used.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import ast
from ..errors import SiplSyntaxError
from ..interpreter import UndefinedVariable, eval_aexp, eval_bexp, execute
from ..interpreter.events import (
    BeforeStatement,
    Event,
    ExecutionError,
    ProgramFinished,
)
from ..parser import parse, parse_aexp, parse_bexp

THREAD_ID = 1
VARIABLES_REF = 1
DEFAULT_MAX_STEPS = 100_000
_STATEMENTS = (ast.Assign, ast.Skip, ast.If, ast.While)

Messages = list[dict[str, Any]]


@dataclass
class _Stop:
    event: BeforeStatement | None  # None when stopped on a runtime error
    error: ExecutionError | None = None


def _index_statements(program: ast.Program) -> tuple[dict[int, int], set[int]]:
    """Return ({id(stmt): nesting depth}, {start lines of debuggable statements}).

    Depth counts enclosing If/While statements, so step-over skips nested bodies.
    """
    depth: dict[int, int] = {}
    lines: set[int] = set()

    def walk(node: ast.Stm, d: int) -> None:
        match node:
            case ast.Seq(items=items):
                for it in items:
                    walk(it, d)
            case ast.Block(body=body):
                walk(body, d)
            case ast.If(then=t, orelse=e):
                depth[id(node)] = d
                lines.add(node.span.line)
                walk(t, d + 1)
                walk(e, d + 1)
            case ast.While(body=b):
                depth[id(node)] = d
                lines.add(node.span.line)
                walk(b, d + 1)
            case _:
                depth[id(node)] = d
                lines.add(node.span.line)

    walk(program.body, 0)
    return depth, lines


class DebugSession:
    def __init__(self) -> None:
        self._seq = 0
        self._program: ast.Program | None = None
        self._path = ""
        self._events: Iterator[Event] | None = None
        self._depth: dict[int, int] = {}
        self._stmt_lines: set[int] = set()
        self._breakpoints: set[int] = set()
        self._stop_on_entry = True
        self._current: _Stop | None = None
        self._prev_line = 0
        self._done = False
        self._exit_code = 0
        self._configured = False
        self.finished = False  # True once 'disconnect' handled

    # ---- message helpers ----
    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _response(
        self, req: dict[str, Any], body: dict[str, Any] | None = None, *, error: str | None = None
    ) -> dict[str, Any]:
        r: dict[str, Any] = {
            "seq": self._next_seq(),
            "type": "response",
            "request_seq": req.get("seq", 0),
            "command": req.get("command", ""),
            "success": error is None,
        }
        if error is not None:
            r["message"] = error
        if body is not None:
            r["body"] = body
        return r

    def _event(self, name: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        e: dict[str, Any] = {"seq": self._next_seq(), "type": "event", "event": name}
        if body is not None:
            e["body"] = body
        return e

    def _output(self, text: str, category: str = "console") -> dict[str, Any]:
        return self._event("output", {"category": category, "output": text})

    # ---- dispatch ----
    def handle_request(self, req: dict[str, Any]) -> Messages:
        cmd = req.get("command", "")
        handler = getattr(self, f"_req_{cmd}", None)
        if handler is None:
            return [self._response(req, error=f"unsupported request '{cmd}'")]
        out: Messages = handler(req, req.get("arguments") or {})
        return out

    # ---- requests ----
    def _req_initialize(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        caps = {
            "supportsConfigurationDoneRequest": True,
            "supportsEvaluateForHovers": True,
            "supportsStepBack": False,
            "supportsTerminateRequest": True,
        }
        return [self._response(req, caps), self._event("initialized")]

    def _req_launch(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        path = args.get("program")
        if not isinstance(path, str) or not path:
            return [self._response(req, error="launch: 'program' is required")]
        try:
            source = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            return [self._response(req, error=f"cannot read {path}: {exc.strerror or exc}")]
        try:
            program = parse(source)
        except SiplSyntaxError as exc:
            d = exc.diagnostics[0]
            where = f"{d.span.line}:{d.span.col}" if d.span else "?"
            msg = f"{path}:{where}: {d.message}"
            return [self._output(msg + "\n", "stderr"), self._response(req, error=msg)]
        inputs = args.get("inputs") or {}
        try:
            initial = {str(k): int(v) for k, v in inputs.items()}
            max_steps = int(args.get("maxSteps", DEFAULT_MAX_STEPS))
        except (TypeError, ValueError, AttributeError):
            return [self._response(req, error="launch: 'inputs' must map names to integers")]
        self._program, self._path = program, path
        self._depth, self._stmt_lines = _index_statements(program)
        self._stop_on_entry = bool(args.get("stopOnEntry", True))
        self._events = execute(program, initial, max_steps=max_steps)
        return [self._response(req)]

    def _req_setBreakpoints(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        requested = [int(b["line"]) for b in args.get("breakpoints", []) if "line" in b] or [
            int(x) for x in args.get("lines", [])
        ]
        resolved: list[dict[str, Any]] = []
        self._breakpoints = set()
        for line in requested:
            actual = min((ln for ln in self._stmt_lines if ln >= line), default=None)
            if actual is None:
                resolved.append({"verified": False, "line": line, "message": "no statement here"})
            else:
                self._breakpoints.add(actual)
                resolved.append({"verified": True, "line": actual})
        return [self._response(req, {"breakpoints": resolved})]

    def _req_setExceptionBreakpoints(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        return [self._response(req, {"breakpoints": []})]

    def _req_configurationDone(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        if self._events is None:
            return [self._response(req, error="configurationDone before successful launch")]
        self._configured = True
        out = [self._response(req)]
        out += self._resume("entry" if self._stop_on_entry else None, mode="entry")
        return out

    def _req_threads(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        return [self._response(req, {"threads": [{"id": THREAD_ID, "name": "main"}]})]

    def _req_stackTrace(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        frames: list[dict[str, Any]] = []
        cur = self._current
        span = None
        name = "program"
        if cur is not None and cur.event is not None:
            span, name = cur.event.span, cur.event.stmt_type
        elif cur is not None and cur.error is not None:
            span, name = cur.error.span, "error"
        if span is not None:
            frames.append(
                {
                    "id": 1,
                    "name": name,
                    "source": {"name": Path(self._path).name, "path": self._path},
                    "line": span.line,
                    "column": span.col,
                    "endLine": span.end_line,
                    "endColumn": span.end_col,
                }
            )
        return [self._response(req, {"stackFrames": frames, "totalFrames": len(frames)})]

    def _req_scopes(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        scope = {"name": "Variables", "variablesReference": VARIABLES_REF, "expensive": False}
        return [self._response(req, {"scopes": [scope]})]

    def _state(self) -> dict[str, int]:
        cur = self._current
        if cur is None:
            return {}
        if cur.event is not None:
            return dict(cur.event.state)
        if cur.error is not None:
            return dict(cur.error.state)
        return {}

    def _req_variables(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        variables = [
            {"name": n, "value": str(v), "type": "int", "variablesReference": 0}
            for n, v in sorted(self._state().items())
        ]
        return [self._response(req, {"variables": variables})]

    def _req_evaluate(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        expr = str(args.get("expression", "")).strip()
        state = self._state()
        try:
            try:
                result: str = str(eval_aexp(parse_aexp(expr), state))
            except SiplSyntaxError:
                result = str(eval_bexp(parse_bexp(expr), state)).lower()
        except SiplSyntaxError as exc:
            return [self._response(req, error=f"syntax error: {exc.diagnostics[0].message}")]
        except UndefinedVariable as exc:
            return [self._response(req, error=f"variable '{exc.name}' is not defined")]
        return [self._response(req, {"result": result, "variablesReference": 0})]

    def _req_continue(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        return [self._response(req, {"allThreadsContinued": True}), *self._resume(None, "continue")]

    def _req_next(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        return [self._response(req), *self._resume("step", "next")]

    def _req_stepIn(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        return [self._response(req), *self._resume("step", "in")]

    def _req_stepOut(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        return [self._response(req), *self._resume("step", "out")]

    def _req_pause(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        return [self._response(req, error="pause is not supported")]

    def _req_terminate(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        out = [self._response(req)]
        if not self._done:
            out += self._finish(0)
        return out

    def _req_disconnect(self, req: dict[str, Any], args: dict[str, Any]) -> Messages:
        self.finished = True
        self._events = None
        return [self._response(req)]

    # ---- execution control ----
    def _finish(self, exit_code: int) -> Messages:
        self._done = True
        self._events = None
        self._current = None
        return [
            self._event("exited", {"exitCode": exit_code}),
            self._event("terminated"),
        ]

    def _resume(self, reason: str | None, mode: str) -> Messages:
        """Run until the next stop. `mode`: entry | continue | in | next | out."""
        if self._events is None or self._done:
            return []
        cur = self._current
        if cur is not None and cur.error is not None:  # resuming after a runtime error
            return self._finish(self._exit_code)
        start_depth = (
            self._depth.get(id(cur.event.node), 0) if cur and cur.event and cur.event.node else 0
        )
        out: Messages = []
        for ev in self._events:
            if isinstance(ev, BeforeStatement):
                line = ev.span.line if ev.span else 0
                depth = self._depth.get(id(ev.node), 0)
                prev, self._prev_line = self._prev_line, line
                stop_reason: str | None = None
                if mode == "entry":
                    stop_reason = "entry" if reason == "entry" else None
                elif (
                    mode == "in"
                    or mode == "next"
                    and depth <= start_depth
                    or mode == "out"
                    and depth < start_depth
                ):
                    stop_reason = "step"
                if stop_reason is None and line in self._breakpoints and line != prev:
                    stop_reason = "breakpoint"
                if stop_reason is not None:
                    self._current = _Stop(ev)
                    out.append(self._stopped(stop_reason))
                    return out
            elif isinstance(ev, ProgramFinished):
                summary = ", ".join(f"{k}={v}" for k, v in ev.state) or "(empty)"
                out.append(
                    self._output(f"Program finished in {ev.steps} steps: {summary}\n", "stdout")
                )
                return out + self._finish(0)
            elif isinstance(ev, ExecutionError):
                self._exit_code = 2
                self._current = _Stop(None, ev)
                out.append(self._output(f"Runtime error: {ev.message}\n", "stderr"))
                out.append(self._stopped("exception", ev.message))
                return out
        return out + self._finish(0)

    def _stopped(self, reason: str, text: str | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"reason": reason, "threadId": THREAD_ID, "allThreadsStopped": True}
        if text:
            body["text"] = text
            body["description"] = text
        return self._event("stopped", body)
