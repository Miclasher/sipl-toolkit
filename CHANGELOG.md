# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-17

First version. Nothing has been published yet: the tag, GitHub Release and PyPI upload are
done by the maintainer (see `docs/releasing.md`); the package builds and installs from the
wheel.

### Added
- Grammar: Lark LALR grammar for SIPL (`grammar/sipl.lark`) with the textbook rule mapping
  (P1, S1-S6, A1-A6, B1-B5); `or`/`not` aliases for `∨`/`¬`, `#` comments, negative literals,
  multi-character identifiers. At least 10 valid and 10 invalid grammar test programs.
- Parser and AST: own typed, frozen AST with `SourceSpan` on every node; `parse`,
  `parse_aexp`, `parse_bexp`, `check`; syntax errors reported as diagnostics with
  line/column and expected tokens.
- Interpreter: partial state, assignment, sequence, `if`, `while`, `begin/end`, `skip`;
  explicit `undefined-variable` and `step-limit-exceeded` errors; configurable step limit
  (default 100000); iterative statement execution.
- Event model: `program_started`, `before_statement`, `variable_changed`,
  `condition_evaluated`, `after_statement`, `program_finished`, `execution_error`.
- CLI: `sipl parse|check|run|trace` with `--var`, `--max-steps`, stdin input (`-`),
  documented exit codes (0, 1, 2, 64, 66) and a stable `--json` mode (`schema_version` 1,
  JSON Schema in `src/sipl/schemas/`, contract in `docs/json-schema.md`).
- Debug Adapter Protocol server (`sipl-dap`, `python -m sipl.dap`): launch with `inputs`,
  `maxSteps`, `stopOnEntry`; line breakpoints; continue, step in/over/out; variables;
  evaluate (arithmetic and boolean expressions); runtime errors reported as stops.
- VS Code extension (`vscode-sipl/`) with language support and a debug adapter factory.
- Examples (`examples/`, `examples/invalid/`) and a pytest suite (155 tests, 96% coverage),
  ruff and strict mypy configuration.
- Release automation: CI workflow, release workflow, `scripts/check_version.py`,
  `docs/releasing.md`.
- Documentation: README, `docs/language.md`, `docs/architecture.md`, `docs/debugging.md`,
  `docs/defense.md`.

### Known limitations
- Line breakpoints deduplicate consecutive stops on the same source line.
- Single stack frame; `pause` and step back are not supported.
- Expression evaluation is recursive and can hit the Python recursion limit on extremely
  deep expressions.
- The VS Code F5 flow is verified only against a mock host and the DAP tests, not in a real
  VS Code window.
- The CI workflow has not yet run on GitHub.

[Unreleased]: https://github.com/OWNER/REPO/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/REPO/releases/tag/v0.1.0
