import subprocess
import sys
from pathlib import Path

from sipl.dap.protocol import read_message, write_message
from sipl.dap.session import DebugSession

EX = Path(__file__).resolve().parent.parent / "examples"
POWER = str(EX / "power.sipl")


class Client:
    """Scripted DAP client driving a DebugSession directly."""

    def __init__(self) -> None:
        self.s = DebugSession()
        self.seq = 0
        self.events: list[dict] = []

    def call(self, command, **arguments):
        self.seq += 1
        msgs = self.s.handle_request(
            {"seq": self.seq, "type": "request", "command": command, "arguments": arguments}
        )
        resp = next(m for m in msgs if m["type"] == "response")
        self.events = [m for m in msgs if m["type"] == "event"]
        return resp

    def stopped(self):
        return next((e["body"] for e in self.events if e["event"] == "stopped"), None)

    def event_names(self):
        return [e["event"] for e in self.events]

    def frame(self):
        return self.call("stackTrace", threadId=1)["body"]["stackFrames"][0]

    def variables(self):
        r = self.call("variables", variablesReference=1)
        return {v["name"]: v["value"] for v in r["body"]["variables"]}

    def start(self, program=POWER, inputs=None, bps=(), **launch):
        assert self.call("initialize", adapterID="sipl")["success"]
        assert "initialized" in self.event_names()
        r = self.call("launch", program=program, inputs=inputs or {}, **launch)
        assert r["success"], r
        if bps:
            self.call(
                "setBreakpoints", source={"path": program}, breakpoints=[{"line": b} for b in bps]
            )
        self.call("configurationDone")


def test_stop_on_entry_and_variables():
    c = Client()
    c.start(inputs={"X": 5, "Y": 2})
    assert c.stopped()["reason"] == "entry"
    f = c.frame()
    assert (f["line"], f["column"], f["name"]) == (3, 3, "Assign")
    assert f["source"]["path"] == POWER
    assert c.variables() == {"X": "5", "Y": "2"}


def test_breakpoint_continue_and_state():
    c = Client()
    c.start(inputs={"X": 5, "Y": 2}, bps=[6], stopOnEntry=False)
    assert c.stopped()["reason"] == "breakpoint" and c.frame()["line"] == 6
    assert c.variables() == {"R": "1", "X": "5", "Y": "2"}
    c.call("continue", threadId=1)
    assert c.stopped()["reason"] == "breakpoint"
    assert c.variables() == {"R": "5", "X": "5", "Y": "1"}
    c.call("continue", threadId=1)
    assert "terminated" in c.event_names()


def test_breakpoint_moves_to_next_statement_line():
    c = Client()
    c.start(bps=[1], stopOnEntry=False)  # line 1 is a comment
    # (re-issue to read the response)
    r = c.call("setBreakpoints", source={"path": POWER}, breakpoints=[{"line": 1}, {"line": 99}])
    bps = r["body"]["breakpoints"]
    assert bps[0] == {"verified": True, "line": 3}
    assert bps[1]["verified"] is False


def test_step_in_next_out_and_finish():
    c = Client()
    c.start(inputs={"X": 2, "Y": 1})
    assert c.frame()["line"] == 3
    c.call("next", threadId=1)
    assert c.frame()["line"] == 4 and c.frame()["name"] == "While"
    c.call("next", threadId=1)  # steps over the whole loop -> program ends
    assert "terminated" in c.event_names()
    out = [e["body"]["output"] for e in c.events if e["event"] == "output"]
    assert "R=2" in out[0]


def test_step_in_enters_loop_body_and_out_leaves():
    c = Client()
    c.start(inputs={"X": 2, "Y": 2})
    c.call("stepIn", threadId=1)
    c.call("stepIn", threadId=1)
    assert c.frame()["line"] == 6
    c.call("stepOut", threadId=1)
    assert "terminated" in c.event_names()  # nothing after the loop


def test_evaluate_arith_bool_errors():
    c = Client()
    c.start(inputs={"X": 5, "Y": 2})
    assert c.call("evaluate", expression="X * 2 + 1", context="repl")["body"]["result"] == "11"
    assert c.call("evaluate", expression="X > Y", context="hover")["body"]["result"] == "true"
    assert not c.call("evaluate", expression="Q + 1")["success"]
    assert not c.call("evaluate", expression="X +")["success"]


def test_runtime_error_stops_with_exception_then_terminates():
    c = Client()
    c.start(program=str(EX / "invalid/undefined_var.sipl"), stopOnEntry=False)
    assert c.stopped()["reason"] == "exception"
    assert "not defined" in c.stopped()["text"]
    assert c.frame()["line"] == 3
    c.call("continue", threadId=1)
    assert "terminated" in c.event_names()


def test_step_limit_reported():
    c = Client()
    c.start(program=str(EX / "infinite.sipl"), stopOnEntry=False, maxSteps=20)
    assert c.stopped()["reason"] == "exception" and "step limit" in c.stopped()["text"]


def test_launch_errors():
    c = Client()
    c.call("initialize")
    assert not c.call("launch")["success"]
    assert not c.call("launch", program="/nonexistent.sipl")["success"]
    r = c.call("launch", program=str(EX / "invalid/missing_end.sipl"))
    assert not r["success"] and ":6:1" in r["message"]
    assert not c.call("launch", program=POWER, inputs={"X": "abc"})["success"]
    assert not c.call("configurationDone")["success"]


def test_misc_requests():
    c = Client()
    c.start(inputs={"X": 1, "Y": 1})
    assert c.call("threads")["body"]["threads"][0]["id"] == 1
    assert c.call("scopes", frameId=1)["body"]["scopes"][0]["variablesReference"] == 1
    assert c.call("setExceptionBreakpoints", filters=[])["success"]
    assert not c.call("pause")["success"]
    assert not c.call("bogus")["success"]
    assert c.call("terminate")["success"] and "terminated" in c.event_names()
    assert c.call("disconnect")["success"] and c.s.finished


def test_if_line_breakpoint_not_hit_twice_on_same_line():
    c = Client()
    c.start(program=str(EX / "gcd.sipl"), inputs={"A": 4, "B": 2}, bps=[4], stopOnEntry=False)
    assert c.stopped()["reason"] == "breakpoint"
    c.call("continue", threadId=1)  # If and its Assign share line 4; must not re-hit
    assert c.stopped() is None and "terminated" in c.event_names()


def test_framing_roundtrip(tmp_path):
    import io

    buf = io.BytesIO()
    write_message(buf, {"seq": 1, "type": "request", "command": "ünï"})
    buf.seek(0)
    assert read_message(buf)["command"] == "ünï"
    assert read_message(buf) is None
    assert read_message(io.BytesIO(b"Content-Length: 50\r\n\r\n{}")) is None


def test_stdio_server_end_to_end():
    proc = subprocess.Popen(
        [sys.executable, "-m", "sipl.dap"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdin and proc.stdout

    def send(seq, command, **arguments):
        write_message(
            proc.stdin, {"seq": seq, "type": "request", "command": command, "arguments": arguments}
        )

    def read_until(pred):
        while True:
            m = read_message(proc.stdout)
            assert m is not None
            if pred(m):
                return m

    send(1, "initialize")
    read_until(lambda m: m.get("event") == "initialized")
    send(2, "launch", program=POWER, inputs={"X": 3, "Y": 2}, stopOnEntry=False)
    send(3, "setBreakpoints", breakpoints=[{"line": 6}])
    send(4, "configurationDone")
    stopped = read_until(lambda m: m.get("event") == "stopped")
    assert stopped["body"]["reason"] == "breakpoint"
    send(5, "variables", variablesReference=1)
    vars_ = read_until(lambda m: m.get("command") == "variables")
    assert {v["name"]: v["value"] for v in vars_["body"]["variables"]} == {
        "R": "1",
        "X": "3",
        "Y": "2",
    }
    send(6, "disconnect")
    read_until(lambda m: m.get("command") == "disconnect")
    proc.stdin.close()
    assert proc.wait(timeout=10) == 0
    proc.stdout.close()
    proc.stderr.close()
