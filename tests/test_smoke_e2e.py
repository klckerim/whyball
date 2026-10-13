"""End-to-end smoke test: a real uvicorn process serves the API and the UI from one port.

By default the UI is a stand-in index.html, so `pytest` runs without Node. With
WHYBALL_SMOKE_DIST=web/dist (`cd web && npm run smoke`) it runs against the real Vite build and
also fetches the script the page loads.
"""

import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    dist = os.environ.get("WHYBALL_SMOKE_DIST")
    if dist:
        static = (REPO_ROOT / dist).resolve()
        assert (static / "index.html").is_file(), f"{static} has no build; run npm run build in web/"
    else:
        static = tmp_path_factory.mktemp("dist")
        (static / "index.html").write_text(
            '<!doctype html><html><body><div id="root"></div></body></html>', encoding="utf-8")
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=REPO_ROOT, env={**os.environ, "WHYBALL_STATIC_DIR": str(static)},
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while True:
            try:
                if httpx.get(f"{base}/api/health", timeout=1).status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if proc.poll() is not None or time.monotonic() > deadline:
                proc.kill()
                pytest.fail("uvicorn did not start:\n" + proc.stdout.read().decode(errors="replace"))
            time.sleep(0.1)
        yield base, bool(dist)
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def test_home_page(server):
    base, real = server
    r = httpx.get(f"{base}/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert '<div id="root"></div>' in r.text
    if real:
        scripts = re.findall(r'<script[^>]+src="(/assets/[^"]+\.js)"', r.text)
        assert scripts, "the built page loads no script"
        js = httpx.get(base + scripts[0])
        assert js.status_code == 200 and "javascript" in js.headers["content-type"]


def test_matches_api(server):
    base, _ = server
    r = httpx.get(f"{base}/api/matches")
    assert r.status_code == 200
    body = r.json()
    assert {m["id"] for m in body} == {"dominant_loss_seed7", "natural_seed100", "red_card_swing_seed42"}
    assert all(m["moments"] > 0 and set(m["sources"]) == {"llm", "template", "template_fallback"} for m in body)


def test_replay_streams_over_http(server):
    base, _ = server
    with httpx.stream("GET", f"{base}/api/matches/natural_seed100/replay",
                      params={"speed": 0, "from_t": 5400}, timeout=10) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        kinds = [line.split(": ", 1)[1] for line in r.iter_lines() if line.startswith("event: ")]
    assert "moment" in kinds and kinds[-1] == "end"
