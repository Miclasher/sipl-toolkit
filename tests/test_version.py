"""Version consistency between pyproject.toml and the package."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check_version.py"


def _load():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("check_version", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_versions_consistent() -> None:
    assert _load().check() == []


def test_tag_matching() -> None:
    mod = _load()
    v = mod.pyproject_version()
    assert mod.check(f"v{v}") == []
    assert mod.check("v999.0.0") != []
