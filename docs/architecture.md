# Architecture

## Key principle: one parser, one interpreter

Every front end (CLI, JSON output, debugger, any future language server) goes through the
same two components: `sipl.parser.parse` and `sipl.interpreter.execute`. Nothing
re-implements parsing or evaluation. Front ends differ only in how they consume the
**event stream**.

## Data flow

```
 source text
     |
     v
 grammar/sipl.lark --(Lark LALR)--> parse tree      (private to parser.py, never leaks)
     |
     v  _Builder transformer
 sipl.ast  (frozen dataclasses, every node has a SourceSpan)
     |
     v
 interpreter.execute(program, initial_state, max_steps)  -> lazy Iterator[Event]
     |
     +--> cli.run      drains the stream, prints the final state
     +--> cli.trace    prints / serializes every event
     +--> dap.session  pulls events one at a time, pauses on BeforeStatement
```

Syntax errors never reach the interpreter: Lark exceptions are converted in `parser.py` to
`Diagnostic` objects (`code`, `message`, `span`, `severity`, `expected`) wrapped in
`SiplSyntaxError`. Runtime problems are not exceptions at the API boundary: they appear as a
terminal `ExecutionError` event.

## Module map

| Module | Responsibility |
|---|---|
| `grammar/sipl.lark` | the grammar (CORE-01); also packaged into the wheel as `sipl/sipl.lark` |
| `sipl/spans.py` | `SourceSpan(start, end, line, col, end_line, end_col)`; 1-based lines/columns, 0-based end-exclusive offsets |
| `sipl/ast.py` | typed AST: `Program, Assign, Seq, If, While, Block, Skip, Num, Var, BinOp, ParenA, Cmp, Or, Not, ParenB` |
| `sipl/errors.py` | `Diagnostic`, `SiplSyntaxError` |
| `sipl/parser.py` | `parse` (program), `parse_aexp`, `parse_bexp` (used by debugger `evaluate`), `check`; converts parse errors to diagnostics |
| `sipl/serialize.py` | AST to text tree and to JSON |
| `sipl/interpreter/state.py` | immutable sorted snapshots of the state |
| `sipl/interpreter/evaluator.py` | `eval_aexp`, `eval_bexp`, `UndefinedVariable` |
| `sipl/interpreter/events.py` | event dataclasses, each with `to_json()` |
| `sipl/interpreter/runner.py` | `execute` (event generator), `run` (drains it to a `RunResult`) |
| `sipl/cli.py` | argument parsing, exit codes, text/JSON output |
| `sipl/dap/protocol.py` | `Content-Length` framing over byte streams |
| `sipl/dap/server.py` | stdio loop: read request, `session.handle_request`, write replies |
| `sipl/dap/session.py` | `DebugSession`: breakpoints, stepping, variables, evaluate |
| `sipl/schemas/cli-output.schema.json` | JSON Schema of the CLI documents |
| `vscode-sipl/` | VS Code extension: language contribution plus a debug adapter factory that spawns `python -m sipl.dap` |

### Design points

- **Spans everywhere.** AST nodes carry exact spans; `Assign` additionally keeps
  `target_span` so `variable_changed` events point at the assigned name. Breakpoints,
  stack frames, diagnostics and trace events all reuse these spans.
- **Seq is flat.** `S1 ; S2 ; S3` is one node with a tuple of items.
- **Interpreter is a generator with an explicit stack.** It keeps a list of frames
  (`run`, `after`, `check`) instead of recursing over statements. Deeply nested or long
  programs and long loops therefore cannot overflow the Python stack, and the generator can
  be suspended after any event, which is what the debugger needs. No threads are used.
  (Expression evaluation is still recursive, see the limitation in the README.)
- **Snapshots are immutable.** Events carry the state as a sorted tuple of pairs; consumers
  can keep them without copying concerns.

## Event model

Events are emitted in this order per statement. `step` is the running step counter (see
`docs/language.md`).

| Event (`kind`) | Fields | When |
|---|---|---|
| `ProgramStarted` (`program_started`) | `state` | once, first |
| `BeforeStatement` (`before_statement`) | `stmt`, `span`, `state`, `step` | on entering `Assign`, `Skip`, `If`, `While` (not `Seq`/`Block`) |
| `VariableChanged` (`variable_changed`) | `name`, `old` (null if new), `new`, `span` | after an assignment's value is computed, before `AfterStatement` |
| `ConditionEvaluated` (`condition_evaluated`) | `owner` (`If`/`While`), `value`, `span` | every time a condition is evaluated, incl. each loop check |
| `AfterStatement` (`after_statement`) | `stmt`, `span`, `state`, `step` | when the statement completes; for `If` and `While` after the branch/loop finished |
| `ProgramFinished` (`program_finished`) | `state`, `steps` | terminal, success |
| `ExecutionError` (`execution_error`) | `code`, `message`, `span`, `state`, `steps` | terminal, failure (`undefined-variable`, `division-by-zero`, `step-limit-exceeded`) |

Exactly one terminal event ends every stream. `Before`/`After` pairs nest properly and share
the same `step` number, as the `trace` output for `power` shows:

```
[2] -> While @4:3 ...
  While condition @4:9 = true
[3] -> Assign @6:5 ...
...
[2] <- While @4:3 ...
```

JSON shapes are in `docs/json-schema.md` and `src/sipl/schemas/cli-output.schema.json`.

## Extension points

- **New statement or expression.** Add a rule in `grammar/sipl.lark`, a node in `ast.py`, a
  builder method in `parser.py`, a case in `serialize.py`, and evaluation in
  `evaluator.py` / `runner.py`. Update the JSON schema (additive within `schema_version`
  1) and `docs/language.md`.
- **New event kind.** Add a dataclass with `to_json()` in `events.py`, emit it in
  `runner.py`, document it in the schema. Consumers that ignore unknown kinds keep working.
- **New front end** (language server, web UI, visualizer): call `parse`, then iterate
  `execute(...)`. Do not copy evaluation logic.
- **New DAP request**: add a `_req_<name>` method to `DebugSession`; dispatch is by name.
- **Alternative semantics** (for instance short-circuit `or`, bounded integers): confined to
  `evaluator.py`.
