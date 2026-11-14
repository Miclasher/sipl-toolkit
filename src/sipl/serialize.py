"""Generic AST -> JSON-compatible dict, used by the CLI and visualizers."""

from __future__ import annotations

import dataclasses
from typing import Any

from .ast import Node
from .spans import SourceSpan


def ast_to_json(node: Any) -> Any:
    if isinstance(node, SourceSpan):
        return node.to_json()
    if isinstance(node, Node):
        out: dict[str, Any] = {"type": type(node).__name__}
        for f in dataclasses.fields(node):
            out[f.name] = ast_to_json(getattr(node, f.name))
        return out
    if isinstance(node, tuple | list):
        return [ast_to_json(x) for x in node]
    return node


def ast_to_text(node: Node, indent: int = 0) -> str:
    """Indented human-readable tree with source positions."""
    pad = "  " * indent
    sp = node.span
    scalars = []
    children: list[tuple[str, Any]] = []
    for f in dataclasses.fields(node):
        if f.name in ("span", "target_span"):
            continue
        v = getattr(node, f.name)
        if isinstance(v, Node) or (isinstance(v, tuple) and v and isinstance(v[0], Node)):
            children.append((f.name, v))
        else:
            scalars.append(f"{f.name}={v!r}")
    head = f"{pad}{type(node).__name__}"
    if scalars:
        head += " " + " ".join(scalars)
    head += f"  @{sp.line}:{sp.col}-{sp.end_line}:{sp.end_col}"
    lines = [head]
    for _, v in children:
        for child in v if isinstance(v, tuple) else (v,):
            lines.append(ast_to_text(child, indent + 1))
    return "\n".join(lines)
