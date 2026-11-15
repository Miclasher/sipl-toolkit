"""Debug Adapter Protocol server over stdio: `python -m sipl.dap` / `sipl-dap`."""

from __future__ import annotations

import sys
from typing import BinaryIO

from .protocol import read_message, write_message
from .session import DebugSession


def serve(inp: BinaryIO, out: BinaryIO) -> None:
    session = DebugSession()
    while not session.finished:
        msg = read_message(inp)
        if msg is None:
            break
        if msg.get("type") != "request":
            continue
        for reply in session.handle_request(msg):
            write_message(out, reply)


def main() -> int:
    serve(sys.stdin.buffer, sys.stdout.buffer)
    return 0


if __name__ == "__main__":
    sys.exit(main())
