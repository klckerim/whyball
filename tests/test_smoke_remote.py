"""scripts/smoke_remote.py against the local server, and against deliberately broken servers."""

import importlib.util
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from tests.test_smoke_e2e import server  # noqa: F401  (module-scoped fixture: a real uvicorn process)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "smoke_remote.py"
spec = importlib.util.spec_from_file_location("smoke_remote", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def test_passes_against_the_local_server(server, capsys):  # noqa: F811
    base, _ = server
    assert smoke.main([base, "--events", "5"]) == 0
    out = capsys.readouterr().out
    for name in ("healthz", "matches", "deep-link", "sse-events", "sse-progressive", "trace-sse", "verification", "total-time"):
        assert f"PASS {name}:" in out
    assert "ALL PASSED" in out and "FAIL" not in out


class Fake(BaseHTTPRequestHandler):
    """buffered=True sends the whole SSE body at the end (what a buffering proxy does)."""
    buffered = False
    matches = 3
    traces = True  # the replay carries stored trace events
    verification = True  # the moment cards carry a verification field

    def log_message(self, *a):
        pass

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/healthz":
            self._send(b'{"ok": true, "matches": 3}', "application/json")
        elif self.path == "/api/matches":
            ids = ["red_card_swing_seed42", *[f"m{i}" for i in range(1, self.matches)]]
            self._send(json.dumps([{"id": i} for i in ids[:self.matches]]).encode(), "application/json")
        elif self.path.endswith("/moments"):
            v = {"guard": True, "verifier": "passed", "attempts": 1, "label_source": "llm"}
            cards = [{"id": f"c{i}", **({"verification": v} if self.verification else {})} for i in range(3)]
            self._send(json.dumps(cards).encode(), "application/json")
        elif self.path.startswith("/match/"):
            self._send(b'<div id="root"></div>', "text/html; charset=utf-8")
        elif "/replay" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            events = [f"event: match_event\ndata: {json.dumps({'t': i * 6})}\n\n".encode() for i in range(6)]
            if self.traces:
                events.append(b'event: trace\ndata: {"step": "narrate"}\n\n')
            events.append(b"event: end\ndata: {}\n\n")
            if self.buffered:
                time.sleep(1.2)
                self.wfile.write(b"".join(events))
            else:
                for e in events:
                    self.wfile.write(e)
                    self.wfile.flush()
                    time.sleep(0.2)
            self.close_connection = True
        else:
            self.send_error(404)


def fake_server(**attrs):
    handler = type("H", (Fake,), attrs)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


@pytest.mark.parametrize("attrs, failing", [
    ({}, None),
    ({"buffered": True}, "sse-progressive"),
    ({"matches": 2}, "matches"),
    ({"traces": False}, "trace-sse"),
    ({"verification": False}, "verification"),
])
def test_fake_servers(attrs, failing):
    httpd = fake_server(**attrs)
    try:
        results = smoke.run(f"http://127.0.0.1:{httpd.server_port}", events=5, speed=30.0, timeout=5)
    finally:
        httpd.shutdown()
    assert [n for ok, n, _ in results if not ok] == ([failing] if failing else [])


def test_unreachable_server_fails_cleanly(capsys):
    assert smoke.main(["http://127.0.0.1:9", "--timeout", "1"]) == 1
    assert "FAIL request:" in capsys.readouterr().out


def test_wait_succeeds_once_the_server_comes_up():
    # Reserve a port, start answering on it only after 1.5 s: the first attempts are connection errors.
    probe = ThreadingHTTPServer(("127.0.0.1", 0), Fake)
    port = probe.server_port
    probe.server_close()
    holder = {}

    def later():
        time.sleep(1.5)
        holder["httpd"] = ThreadingHTTPServer(("127.0.0.1", port), Fake)
        holder["httpd"].serve_forever()

    threading.Thread(target=later, daemon=True).start()
    try:
        results = smoke.run(f"http://127.0.0.1:{port}", events=5, speed=30.0, timeout=5, wait=10)
    finally:
        if "httpd" in holder:
            holder["httpd"].shutdown()
    assert results[0][1] == "wait" and results[0][0] and "ready after" in results[0][2]
    assert all(ok for ok, _, _ in results)


def test_wait_times_out_with_one_clear_fail_line(capsys):
    assert smoke.main(["http://127.0.0.1:9", "--wait", "2", "--timeout", "1"]) == 1
    out = capsys.readouterr().out
    assert "FAIL wait: not ready after 2s" in out
    assert "healthz" not in out  # the normal checks are skipped


def test_default_does_not_wait():
    t = time.monotonic()
    results = smoke.run("http://127.0.0.1:9", timeout=1)
    assert [n for _, n, _ in results][0] == "request" and time.monotonic() - t < 3
