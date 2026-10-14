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
    for name in ("healthz", "matches", "deep-link", "sse-events", "sse-progressive", "total-time"):
        assert f"PASS {name}:" in out
    assert "ALL PASSED" in out and "FAIL" not in out


class Fake(BaseHTTPRequestHandler):
    """buffered=True sends the whole SSE body at the end (what a buffering proxy does)."""
    buffered = False
    matches = 3

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
            self._send(json.dumps([{"id": f"m{i}"} for i in range(self.matches)]).encode(), "application/json")
        elif self.path.startswith("/match/"):
            self._send(b'<div id="root"></div>', "text/html; charset=utf-8")
        elif "/replay" in self.path:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Connection", "close")
            self.end_headers()
            events = [f"event: match_event\ndata: {json.dumps({'t': i * 6})}\n\n".encode() for i in range(6)]
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
