"""Grammar-level tests: valid/invalid corpus files under tests/grammar/."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from sipl.errors import SiplSyntaxError
from sipl.parser import check, parse

ROOT = Path(__file__).parent / "grammar"
VALID = sorted((ROOT / "valid").glob("*.sipl"))
INVALID = sorted((ROOT / "invalid").glob("*.sipl"))
EXPECT = re.compile(r"#\s*expect:\s*(\d+):(\d+)\s+(\S+)")


def test_corpus_sizes() -> None:
    assert len(VALID) >= 10
    assert len(INVALID) >= 10


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_files_parse(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    assert check(src) == []
    parse(src)


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_files_report_expected_position(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    m = EXPECT.match(src.splitlines()[0])
    assert m, f"{path.name} lacks a '# expect: line:col code' header"
    line, col, code = int(m[1]), int(m[2]), m[3]

    diags = check(src)
    assert len(diags) == 1
    d = diags[0]
    assert d.span is not None
    assert (d.span.line, d.span.col) == (line, col)
    assert d.code == code
    assert d.severity == "error"
    assert d.message

    with pytest.raises(SiplSyntaxError) as info:
        parse(src)
    assert info.value.diagnostics == diags


def test_error_message_is_friendly() -> None:
    (d,) = check("begin x = 1 end")
    assert d.message == "unexpected '=', expected ':='"
    assert d.expected == ("':='",)
    (d,) = check("begin x := 1; end")
    assert "COLON" not in d.message and "identifier" in d.message
    assert "'if'" in d.expected
