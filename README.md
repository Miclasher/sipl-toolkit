# SIPL Language Toolkit

<!-- CI badge: replace OWNER/REPO after the repository is pushed to GitHub:
[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
-->

A Python toolkit for **SIPL**, the teaching language of the "Theory of Programming" course
(`P ::= begin S end`, assignment, `;`, `if`, `while`, `begin/end`, `skip`).
One parser and one interpreter back every front end: a command-line interface (`parse`, `check`,
`run`, `trace`) with a stable JSON mode, and a Debug Adapter Protocol (DAP) server with a
VS Code extension.

Track: **Interpreter + Debugger**, individual project, Python.

## Claimed tasks and points

| ID | Task | Points | Status |
|---|---|---|---|
| CORE-01 | Machine-readable grammar (Lark), >= 10 positive and >= 10 negative test programs | 0.5 | implemented (`grammar/sipl.lark`, `tests/grammar/`) |
| CORE-02 | Parser, own typed AST with `SourceSpan`, syntax diagnostics with line/column | 1.5 | implemented (`src/sipl/parser.py`, `ast.py`) |
| CORE-03 | Interpreter: state, `:=`, `;`, `if`, `while`, `begin/end`, `skip`, step limit | 2.0 | implemented (`src/sipl/interpreter/`) |
| CORE-04 | Event/trace model | 1.0 | implemented (`interpreter/events.py`) |
| CORE-05 | CLI `parse/check/run/trace`, stable `--json`, integration tests | 1.0 | implemented (`src/sipl/cli.py`) |
| IDE-03 | DAP server + VS Code extension (F5, breakpoints, continue, step, variables, evaluate) | 2.5 | implemented; see limitations for what was verified |
| REL-01 | GitHub Actions CI | 0.5 | workflow written (`.github/workflows/ci.yml`); not yet run on GitHub, nothing has been pushed |
| REL-02 | SemVer, CHANGELOG, tagged release | 0.5 | version 0.1.0 and CHANGELOG ready; the git tag / GitHub Release is published by the maintainer, see `docs/releasing.md` |
| REL-03 | Installable package | 0.5 | package builds and installs from the wheel (verified in a fresh venv); PyPI/GitHub release published by the maintainer, see `docs/releasing.md` |
| | **Total claimed** | **10.0** | |

Honesty note: as of this version nothing has been pushed to GitHub, no release exists and
nothing has been uploaded to PyPI. REL-01/02/03 are claimed on the basis of reproducible
local artifacts and workflows that the maintainer still has to publish.

## Install

Requires Python 3.11 or newer.

```sh
python -m venv .venv
. .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e .[dev]           # development install (tests, ruff, mypy, build tools)
# or, for use only:
pip install .
# or from a built wheel:
pip install dist/sipl_toolkit-0.1.0-py3-none-any.whl
```

This installs two commands: `sipl` (CLI) and `sipl-dap` (debug adapter, same as
`python -m sipl.dap`).

## Quick start

The examples below are real outputs for the files in `examples/`.

### `sipl check FILE` - syntax check

```console
$ sipl check examples/power.sipl
examples/power.sipl: ok
$ sipl check examples/invalid/missing_else.sipl
examples/invalid/missing_else.sipl:3:1: error: unexpected 'end', expected 'else'
$ echo $?
1
```

### `sipl parse FILE` - print the AST with source spans

```console
$ sipl parse examples/power.sipl
Program  @2:1-9:4
  Seq  @3:3-8:6
    Assign target='R'  @3:3-3:9
      Num value=1  @3:8-3:9
    While  @4:3-8:6
      Cmp op='>'  @4:9-4:14
        Var name='Y'  @4:9-4:10
        Num value=0  @4:13-4:14
      Block  @5:3-8:6
        Seq  @6:5-7:15
          Assign target='R'  @6:5-6:15
            BinOp op='*'  @6:10-6:15
              Var name='R'  @6:10-6:11
              Var name='X'  @6:14-6:15
          Assign target='Y'  @7:5-7:15
            BinOp op='-'  @7:10-7:15
              Var name='Y'  @7:10-7:11
              Num value=1  @7:14-7:15
```

### `sipl run FILE [--var NAME=INT]... [--max-steps N]` - execute

```console
$ sipl run examples/power.sipl --var X=5 --var Y=2
R = 25
X = 5
Y = 0
$ sipl run examples/invalid/undefined_var.sipl
examples/invalid/undefined_var.sipl:3:8: runtime error: variable 'Y' is not defined
$ echo $?
2
$ sipl run examples/infinite.sipl --max-steps 50
examples/infinite.sipl:3:3: runtime error: step limit of 50 exceeded
```

### `sipl trace FILE [--var NAME=INT]...` - event trace

```console
$ sipl trace examples/power.sipl --var X=2 --var Y=1
program_started state={'X': 2, 'Y': 1}
[1] -> Assign @3:3 state={'X': 2, 'Y': 1}
  R: None -> 1
[1] <- Assign @3:3 state={'R': 1, 'X': 2, 'Y': 1}
[2] -> While @4:3 state={'R': 1, 'X': 2, 'Y': 1}
  While condition @4:9 = true
[3] -> Assign @6:5 state={'R': 1, 'X': 2, 'Y': 1}
  R: 1 -> 2
[3] <- Assign @6:5 state={'R': 2, 'X': 2, 'Y': 1}
[4] -> Assign @7:5 state={'R': 2, 'X': 2, 'Y': 1}
  Y: 1 -> 0
[4] <- Assign @7:5 state={'R': 2, 'X': 2, 'Y': 0}
  While condition @4:9 = false
[2] <- While @4:3 state={'R': 2, 'X': 2, 'Y': 0}
program_finished state={'R': 2, 'X': 2, 'Y': 0}
```

`-` as the file name reads the program from standard input. `sipl --version` prints
`sipl 0.1.0`.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 1 | syntax error |
| 2 | runtime error (`undefined-variable`, `division-by-zero`) or `step-limit-exceeded` |
| 64 | usage error (bad arguments, e.g. `--var X`) |
| 66 | input file cannot be read |

### JSON mode

Add `--json` to any command to get exactly one JSON document on stdout, for example:

```console
$ sipl run examples/power.sipl --var X=5 --var Y=2 --json
{
  "schema_version": 1,
  "command": "run",
  "file": "examples/power.sipl",
  "ok": true,
  "status": "ok",
  "state": { "R": 25, "X": 5, "Y": 0 },
  "steps": 8,
  "error": null
}
```

(The real output is pretty-printed with one field per line.) The contract is described in
[`docs/json-schema.md`](docs/json-schema.md); the machine-readable schema is
`src/sipl/schemas/cli-output.schema.json`.

## Debugging in VS Code

1. `pip install sipl-toolkit` (or `pip install -e .` from this repository) in the Python that
   VS Code will use. The extension starts `python -m sipl.dap`.
2. Install or load the extension from `vscode-sipl/` (open that folder in VS Code and press F5
   to start an Extension Host; see `vscode-sipl/README.md`).
3. Open a `.sipl` file, set breakpoints in the gutter, press **F5**. With no `launch.json` a
   default configuration is used. A custom one:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "sipl",
      "request": "launch",
      "name": "Debug SIPL program",
      "program": "${file}",
      "inputs": { "X": 5, "Y": 2 },
      "maxSteps": 100000,
      "stopOnEntry": true
    }
  ]
}
```

`inputs` are the initial variable values, `maxSteps` the step limit, `stopOnEntry` whether to
stop on the first statement. Details: [`docs/debugging.md`](docs/debugging.md).

## Project layout

```
grammar/sipl.lark          Lark grammar (+ grammar/README.md: textbook rule mapping)
src/sipl/spans.py          SourceSpan
src/sipl/ast.py            typed AST (frozen dataclasses)
src/sipl/errors.py         Diagnostic, SiplSyntaxError
src/sipl/parser.py         Lark parser -> own AST, diagnostics
src/sipl/interpreter/      state, evaluator, events, runner (lazy event generator)
src/sipl/serialize.py      AST -> text / JSON
src/sipl/cli.py            sipl parse|check|run|trace
src/sipl/dap/              DAP server (stdio) and debug session
src/sipl/schemas/          JSON schema of CLI output
vscode-sipl/               VS Code extension (plain JS, no build step)
examples/                  sample programs, examples/invalid/ for error cases
tests/                     pytest suite, tests/grammar/{valid,invalid}/
docs/                      language, architecture, debugging, json-schema, releasing, defense
```

## Tests and quality checks

```sh
pytest                        # 155 tests
pytest --cov=sipl             # coverage (96% total when last measured)
ruff check .
ruff format --check .
mypy                          # strict, configured in pyproject.toml
```

CI (`.github/workflows/ci.yml`) runs the same checks on Python 3.11-3.14 plus a package
build and a wheel smoke test.

## Documentation

- [`docs/language.md`](docs/language.md): grammar, precedence decisions, semantics
- [`docs/architecture.md`](docs/architecture.md): data flow, event model, extension points
- [`docs/debugging.md`](docs/debugging.md): DAP requests and stepping semantics
- [`docs/json-schema.md`](docs/json-schema.md): CLI JSON contract
- [`docs/releasing.md`](docs/releasing.md): release procedure
- [`docs/defense.md`](docs/defense.md): defense script, demo programs, theory notes

## Limitations

- A line breakpoint does not re-trigger for a statement nested *inside* the statement that
  just matched on the same line (e.g. `if c then x := 1 else x := 2` on one line stops once,
  at the `if`). A loop body that repeats stops on every iteration. Stepping is unaffected.
- A breakpoint on a blank/comment line slides to the next statement line, however far.
- The debugger exposes a single stack frame (the current statement); there is no call stack
  because SIPL has no procedures.
- `pause` is not supported (execution is a synchronous pull of events, there is no thread to
  interrupt). Use the step limit to stop runaway programs.
- Expression evaluation is recursive in the depth of the expression: an extremely deeply
  nested expression (thousands of nested parentheses or operators) can hit the Python
  recursion limit. Statement execution itself is iterative and not affected.
- Integers are unbounded; there are no overflow semantics.
- The VS Code F5 flow was verified only against a mock host and the scripted DAP tests
  (`tests/test_dap.py`); it has not been exercised in a real VS Code window.
- CI, GitHub Release and PyPI publication have not been run (nothing has been pushed).

## License

MIT, see `LICENSE`.
