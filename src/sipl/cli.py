"""Command-line interface: sipl parse | check | run | trace.

Exit codes: 0 success, 1 syntax error, 2 runtime error / step limit exceeded,
64 usage error, 66 input file unreadable. With --json a single JSON document
(schema_version 1, see docs/json-schema.md) is written to stdout.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from . import __version__
from .ast import Program
from .errors import Diagnostic, SiplSyntaxError
from .interpreter import execute
from .interpreter.events import ExecutionError, ProgramFinished
from .parser import parse
from .serialize import ast_to_json, ast_to_text

SCHEMA_VERSION = 1
EXIT_OK, EXIT_SYNTAX, EXIT_RUNTIME, EXIT_USAGE, EXIT_NOINPUT = 0, 1, 2, 64, 66
DEFAULT_MAX_STEPS = 100_000


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _fmt_diag(path: str, d: Diagnostic) -> str:
    loc = f"{d.span.line}:{d.span.col}" if d.span else "?"
    return f"{path}:{loc}: {d.severity}: {d.message}"


def _emit(doc: dict[str, Any]) -> None:
    doc = {"schema_version": SCHEMA_VERSION, **doc}
    json.dump(doc, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def _parse_var(text: str) -> tuple[str, int]:
    name, sep, value = text.partition("=")
    if not sep or not name.strip():
        raise argparse.ArgumentTypeError(f"expected NAME=INT, got {text!r}")
    try:
        return name.strip(), int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"value of {name!r} is not an integer: {value!r}"
        ) from None


def _load(args: argparse.Namespace) -> tuple[Program | None, int]:
    """Parse the input file; prints diagnostics and returns (program, exit_code)."""
    try:
        source = _read(args.file)
    except (OSError, UnicodeDecodeError) as exc:
        reason = exc.strerror if isinstance(exc, OSError) else "file is not valid UTF-8"
        msg = f"cannot read {args.file}: {reason or exc}"
        if args.json:
            _emit(
                {
                    "command": args.command,
                    "file": args.file,
                    "ok": False,
                    "diagnostics": [
                        {"code": "io-error", "message": msg, "severity": "error", "span": None}
                    ],
                }
            )
        else:
            print(f"sipl: {msg}", file=sys.stderr)
        return None, EXIT_NOINPUT
    try:
        return parse(source), EXIT_OK
    except SiplSyntaxError as exc:
        if args.json:
            _emit(
                {
                    "command": args.command,
                    "file": args.file,
                    "ok": False,
                    "diagnostics": [d.to_json() for d in exc.diagnostics],
                }
            )
        else:
            for d in exc.diagnostics:
                print(_fmt_diag(args.file, d), file=sys.stderr)
        return None, EXIT_SYNTAX


def _cmd_parse(args: argparse.Namespace) -> int:
    program, code = _load(args)
    if program is None:
        return code
    if args.json:
        _emit({"command": "parse", "file": args.file, "ok": True, "ast": ast_to_json(program)})
    else:
        print(ast_to_text(program))
    return EXIT_OK


def _cmd_check(args: argparse.Namespace) -> int:
    program, code = _load(args)
    if program is None:
        return code
    if args.json:
        _emit({"command": "check", "file": args.file, "ok": True, "diagnostics": []})
    else:
        print(f"{args.file}: ok")
    return EXIT_OK


def _run_events(args: argparse.Namespace, program: Program) -> tuple[list[Any], int]:
    initial = dict(args.var or [])
    events = list(execute(program, initial, max_steps=args.max_steps))
    return events, (EXIT_RUNTIME if isinstance(events[-1], ExecutionError) else EXIT_OK)


def _result_doc(events: list[Any]) -> dict[str, Any]:
    last = events[-1]
    if isinstance(last, ProgramFinished):
        return {"status": "ok", "state": dict(last.state), "steps": last.steps, "error": None}
    assert isinstance(last, ExecutionError)
    return {
        "status": "error",
        "state": dict(last.state),
        "steps": last.steps,
        "error": {
            "code": last.code,
            "message": last.message,
            "span": last.span.to_json() if last.span else None,
        },
    }


def _cmd_run(args: argparse.Namespace) -> int:
    program, code = _load(args)
    if program is None:
        return code
    events, code = _run_events(args, program)
    result = _result_doc(events)
    if args.json:
        _emit({"command": "run", "file": args.file, "ok": code == EXIT_OK, **result})
    elif code == EXIT_OK:
        for name, value in sorted(result["state"].items()):
            print(f"{name} = {value}")
    else:
        err = result["error"]
        sp = err["span"]
        loc = f"{sp['line']}:{sp['col']}" if sp else "?"
        print(f"{args.file}:{loc}: runtime error: {err['message']}", file=sys.stderr)
    return code


def _fmt_event(e: Any) -> str:
    d = e.to_json()
    kind = d["kind"]
    sp = d.get("span")
    at = f"@{sp['line']}:{sp['col']}" if sp else ""
    if kind == "variable_changed":
        return f"  {d['name']}: {d['old']} -> {d['new']}"
    if kind == "condition_evaluated":
        return f"  {d['owner']} condition {at} = {str(d['value']).lower()}"
    if kind in ("before_statement", "after_statement"):
        arrow = "->" if kind == "before_statement" else "<-"
        return f"[{d['step']}] {arrow} {d['stmt']} {at} state={d['state']}"
    if kind == "execution_error":
        return f"ERROR {d['code']}: {d['message']}"
    return f"{kind} state={d.get('state')}"


def _cmd_trace(args: argparse.Namespace) -> int:
    program, code = _load(args)
    if program is None:
        return code
    events, code = _run_events(args, program)
    if args.json:
        _emit(
            {
                "command": "trace",
                "file": args.file,
                "ok": code == EXIT_OK,
                **_result_doc(events),
                "events": [e.to_json() for e in events],
            }
        )
    else:
        for e in events:
            print(_fmt_event(e))
    return code


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sipl", description="SIPL language toolkit")
    p.add_argument("--version", action="version", version=f"sipl {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def common(sp: argparse.ArgumentParser, *, runs: bool) -> None:
        sp.add_argument("file", help="SIPL source file, or '-' for stdin")
        sp.add_argument("--json", action="store_true", help="machine-readable JSON output")
        if runs:
            sp.add_argument(
                "--var",
                "-v",
                action="append",
                type=_parse_var,
                metavar="NAME=INT",
                help="initial value of a variable (repeatable)",
            )
            sp.add_argument(
                "--max-steps",
                type=int,
                default=DEFAULT_MAX_STEPS,
                help=f"step limit (default {DEFAULT_MAX_STEPS})",
            )

    for name, fn, runs, doc in (
        ("parse", _cmd_parse, False, "print the AST"),
        ("check", _cmd_check, False, "check syntax"),
        ("run", _cmd_run, True, "execute and print the final state"),
        ("trace", _cmd_trace, True, "execute and print the event trace"),
    ):
        sp = sub.add_parser(name, help=doc, description=doc)
        common(sp, runs=runs)
        sp.set_defaults(func=fn)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) and code == 0 else EXIT_USAGE
    if getattr(args, "max_steps", 1) < 1:
        print("sipl: --max-steps must be positive", file=sys.stderr)
        return EXIT_USAGE
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
