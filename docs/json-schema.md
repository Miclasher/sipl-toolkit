# CLI JSON contract (schema_version 1)

`sipl <parse|check|run|trace> FILE --json` writes exactly one JSON document to stdout.
The machine-readable schema is `src/sipl/schemas/cli-output.schema.json`; integration
tests validate every command against it. Within `schema_version` 1 fields are only added, never
renamed or removed.

| Field | Commands | Meaning |
|---|---|---|
| `schema_version` | all | always `1` |
| `command`, `file`, `ok` | all | echo of the command, input path, overall success |
| `diagnostics[]` | parse/check/run/trace on failure to read or parse | `{code, message, severity, span, expected?}` |
| `ast` | parse | AST tree: nodes `{type, span, ...fields}` |
| `status`, `state`, `steps`, `error` | run, trace | `status` is `ok`/`error`; `state` maps variable → int |
| `events[]` | trace | `program_started`, `before_statement`, `variable_changed`, `condition_evaluated`, `after_statement`, `program_finished`, `execution_error` |

`span` = `{start, end, line, col, end_line, end_col}`; lines/columns are 1-based, offsets 0-based, end exclusive.

Exit codes: `0` ok · `1` syntax error · `2` runtime error (`undefined-variable`, `division-by-zero`) or `step-limit-exceeded` · `64` usage error · `66` input unreadable.
Step counting: each Assign, Skip, If and each loop-condition check is one step; `--max-steps` (default 100000) bounds execution.
