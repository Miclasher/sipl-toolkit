# Debugging (Debug Adapter Protocol)

`sipl-dap` (equivalently `python -m sipl.dap`) is a DAP server speaking `Content-Length`
framed JSON over stdin/stdout. `src/sipl/dap/session.py` translates requests into pulls
on the interpreter's event generator (`docs/architecture.md`): the debuggee is the
generator, it is suspended whenever the debugger stops, and there are no threads.

## Launch configuration

```json
{
  "type": "sipl",
  "request": "launch",
  "name": "Debug SIPL program",
  "program": "${file}",
  "inputs": { "X": 5, "Y": 2 },
  "maxSteps": 100000,
  "stopOnEntry": true
}
```

| Property | Meaning |
|---|---|
| `program` | path of the `.sipl` file (required) |
| `inputs` | map name -> integer, the initial state (default empty) |
| `maxSteps` | step limit (default 100000) |
| `stopOnEntry` | stop at the first statement (default `true`) |

A syntax error in the program makes `launch` fail with a message `file:line:col: ...` and an
`output` event on `stderr`. Non-integer `inputs` also fail the launch.

## Supported requests

| Request | Behaviour |
|---|---|
| `initialize` | capabilities: `supportsConfigurationDoneRequest`, `supportsEvaluateForHovers`, `supportsTerminateRequest`; no step back. Followed by the `initialized` event |
| `launch` | parse the program, create the event generator; nothing runs yet |
| `setBreakpoints` | line breakpoints, resolved as described below; replaces the previous set |
| `setExceptionBreakpoints` | accepted, no filters |
| `configurationDone` | starts execution: stops at the first statement if `stopOnEntry`, otherwise runs to the first breakpoint or the end |
| `threads` | one thread, id 1, `main` |
| `stackTrace` | one frame (the statement about to execute) with source path, line, column, end line/column |
| `scopes` | one scope, `Variables` |
| `variables` | the current state, sorted by name, all of type `int` |
| `evaluate` | evaluate an expression in the current state (see below) |
| `continue`, `next`, `stepIn`, `stepOut` | resume, see stepping |
| `terminate` | ends the session with `exited` and `terminated` |
| `disconnect` | drops the generator and stops the server loop |
| `pause` | answered with an error response: not supported |

Other requests get an error response `unsupported request`.

Events sent: `initialized`, `stopped` (`entry`, `step`, `breakpoint`, `exception`), `output`
(`stdout`: final summary such as `Program finished in 8 steps: R=25, X=5, Y=0`; `stderr`:
runtime and launch errors), `exited` (exit code 0, or 2 after a runtime error), `terminated`.

## Where the debugger stops

The debugger stops **before** a statement, on `BeforeStatement` events. The debuggable
statements are `Assign`, `Skip`, `If` and `While`; `Seq` and `Block` never stop. A `While`
statement stops once on entry; its condition re-checks and body statements are separate
events (each body statement stops again on every iteration when stepping). The current
state shown in `variables` is the state before that statement.

## Stepping semantics

Each statement has a **nesting depth** = the number of enclosing `If`/`While` statements
(`begin ... end` blocks and sequences do not count). With `start` the depth of the statement
where the debugger is stopped, the next stop is the first following statement with:

| Request | Stops at the next statement whose depth is |
|---|---|
| `stepIn` | any |
| `next` (step over) | `<= start`, so the bodies of the `If` or `While` you are on are skipped |
| `stepOut` | `< start`, i.e. after leaving the enclosing `If`/`While`; at top level this runs to the end of the program |

All of them also stop at a breakpoint reached on the way. `continue` runs to the next
breakpoint, a runtime error, or the end. Example on `examples/power.sipl`: stopped at the
`While` (line 4, depth 0), `stepIn` goes to `R := R * X` (line 6, depth 1), `next` then goes
to `Y := Y - 1`, and from the `While`, `next` would run the whole loop and stop after it
(there is nothing after it in `power`, so the program finishes).

## Breakpoint resolution

A requested line is resolved to the **first line `>=` the requested one on which a
debuggable statement starts**. The response reports the resolved line and `verified: true`;
a line past the last statement is returned as `verified: false`. So a breakpoint set on a
comment or blank line moves down to the next statement, and on `begin`/`end` lines of a
block it moves to the next statement line. A breakpoint triggers on `BeforeStatement` of a
statement starting on that line, except for a statement nested deeper than the immediately
preceding statement on the same line (e.g. the branch of a one-line `if`), so such lines stop
once. Repeated loop-body statements stop on every iteration. Stepping stops are not affected.

## Runtime errors in the debugger

On `undefined-variable` or `step-limit-exceeded` the session stops with reason `exception`
at the span of the error, sends the message on `stderr`, and `variables` shows the state at
the error. The next resume request ends the session with `exited` (exit code 2) and
`terminated`.

## `evaluate`

The expression is parsed with the same grammar (start symbols `aexp` then `bexp`) and
evaluated read-only against the current state:

- arithmetic: `R * X + 1` gives `6` (with R=1, X=5)
- condition: `R > 3` gives `false` (booleans are returned as `true`/`false`)
- an undefined variable gives an error response `variable 'Q' is not defined`
- a syntax error gives `syntax error: ...`

Evaluation cannot change the state. Before the first stop the state is empty. Works for
watch expressions, the debug console and hover.

## Trying it without VS Code

The DAP tests (`tests/test_dap.py`) drive a scripted client over the real framing. In
Python:

```python
from sipl.dap.session import DebugSession

s = DebugSession()
s.handle_request({"seq": 1, "command": "initialize", "arguments": {}})
s.handle_request(
    {
        "seq": 2,
        "command": "launch",
        "arguments": {
            "program": "examples/power.sipl",
            "inputs": {"X": 5, "Y": 2},
            "stopOnEntry": False,
        },
    }
)
s.handle_request(
    {"seq": 3, "command": "setBreakpoints", "arguments": {"breakpoints": [{"line": 6}]}}
)
msgs = s.handle_request({"seq": 4, "command": "configurationDone"})  # ... 'stopped' (breakpoint)
```

## Limitations

Single stack frame; no `pause`; no step back; breakpoint dedupe as above; the VS Code F5
flow has been verified against a mock host and the DAP tests only, not in a real VS Code
window.
