"""DAP wire format: 'Content-Length: N\\r\\n\\r\\n' + JSON body, over byte streams."""

from __future__ import annotations

import json
from typing import Any, BinaryIO


def read_message(stream: BinaryIO) -> dict[str, Any] | None:
    """Read one message; None on clean EOF."""
    length: int | None = None
    while True:
        line = stream.readline()
        if not line:
            return None
        line = line.strip()
        if not line:
            if length is None:
                continue
            break
        name, _, value = line.decode("ascii", "replace").partition(":")
        if name.lower() == "content-length":
            length = int(value.strip())
    body = stream.read(length)
    if len(body) < length:
        return None
    msg = json.loads(body.decode("utf-8"))
    assert isinstance(msg, dict)
    return msg


def write_message(stream: BinaryIO, message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    stream.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    stream.flush()
