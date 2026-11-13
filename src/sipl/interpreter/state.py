"""State helpers: a state is a mapping from variable names to unbounded ints."""

from __future__ import annotations

from collections.abc import Mapping

Snapshot = tuple[tuple[str, int], ...]


def snapshot(state: Mapping[str, int]) -> Snapshot:
    """Immutable, deterministic (sorted) view of a state."""
    return tuple(sorted(state.items()))


def from_snapshot(snap: Snapshot) -> dict[str, int]:
    return dict(snap)
