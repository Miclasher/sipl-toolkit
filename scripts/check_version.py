"""Check that pyproject.toml and sipl.__version__ agree (and optionally a git tag).

Usage: python scripts/check_version.py [TAG]   (a leading "v" on TAG is stripped)
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def pyproject_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(data["project"]["version"])


def package_version() -> str:
    text = (ROOT / "src" / "sipl" / "__init__.py").read_text(encoding="utf-8")
    m = re.search(r"""^__version__\s*=\s*["']([^"']+)["']""", text, re.MULTILINE)
    if not m:
        raise SystemExit("error: __version__ not found in src/sipl/__init__.py")
    return m.group(1)


def check(tag: str | None = None) -> list[str]:
    """Return a list of error messages (empty when everything is consistent)."""
    errors: list[str] = []
    py, pkg = pyproject_version(), package_version()
    if py != pkg:
        errors.append(f"pyproject.toml version {py!r} != sipl.__version__ {pkg!r}")
    if tag is not None:
        want = tag.removeprefix("v")
        if want != py:
            errors.append(f"tag {tag!r} does not match package version {py!r}")
    return errors


def main(argv: list[str]) -> int:
    errors = check(argv[1] if len(argv) > 1 else None)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if not errors:
        print(f"version OK: {pyproject_version()}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
