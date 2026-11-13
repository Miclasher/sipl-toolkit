"""Diagnostics shared by parser, checker and interpreter."""

from __future__ import annotations

from dataclasses import dataclass, field

from .spans import SourceSpan


@dataclass(frozen=True)
class Diagnostic:
    code: str  # e.g. "syntax-error", "unexpected-token", "undefined-variable"
    message: str
    span: SourceSpan | None
    severity: str = "error"  # "error" | "warning"
    expected: tuple[str, ...] = field(default=())

    def to_json(self) -> dict[str, object]:
        out: dict[str, object] = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "span": self.span.to_json() if self.span else None,
        }
        if self.expected:
            out["expected"] = list(self.expected)
        return out


class SiplSyntaxError(Exception):
    """Raised by parser.parse; carries one or more diagnostics."""

    def __init__(self, diagnostics: list[Diagnostic]) -> None:
        self.diagnostics = diagnostics
        super().__init__("; ".join(d.message for d in diagnostics))
