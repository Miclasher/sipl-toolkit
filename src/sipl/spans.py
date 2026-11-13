"""Source positions. Lines and columns are 1-based; offsets are 0-based, end-exclusive."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int
    line: int
    col: int
    end_line: int
    end_col: int

    def to_json(self) -> dict[str, int]:
        return {
            "start": self.start,
            "end": self.end,
            "line": self.line,
            "col": self.col,
            "end_line": self.end_line,
            "end_col": self.end_col,
        }

    def contains_line(self, line: int) -> bool:
        return self.line <= line <= self.end_line
