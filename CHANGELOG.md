# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Release automation: CI workflow, release workflow, `scripts/check_version.py`,
  `docs/releasing.md`.

## [0.1.0] - YYYY-MM-DD

_Skeleton: finalize the date and verify every item before tagging._

### Added
- Grammar and parser: Lark grammar for SIPL and AST construction (in progress).
- Interpreter and events: step-wise execution producing a trace of events (in progress).
- CLI: `sipl` command-line entry point (in progress).
- DAP: `sipl-dap` Debug Adapter Protocol server (planned, not yet implemented).
- VS Code extension: syntax highlighting and debugger wiring (in progress).

[Unreleased]: https://github.com/OWNER/REPO/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/REPO/releases/tag/v0.1.0
