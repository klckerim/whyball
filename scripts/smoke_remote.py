#!/usr/bin/env python3
"""Smoke test for a running WhyBall deployment (standard library only).

    python scripts/smoke_remote.py https://<app-fqdn>  [--events 8] [--speed 30] [--timeout 30] [--wait 0]

Prints one PASS/FAIL line per check and exits 1 if any failed. Checks: /healthz, /api/matches (three
matches), a deep link (HTML), and the replay SSE stream: at least N events, and the first event must
arrive progressively, not all at the end (a buffering proxy delivers the whole stream at once). P2 checks on
red_card_swing_seed42: its replay carries at least one stored `trace` SSE event, and every card of /moments has a
`verification` field (guard, verifier, attempts, label_source).
--wait SECONDS first retries /healthz (once a second) until the server answers, for a container that is
still starting; if it never does, one FAIL line is printed. Default 0: no waiting.
It only reads; it calls no endpoint that spends money.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

EXPECTED_MATCHES = 3
TRACE_MATCH = "red_card_swing_seed42"
VERIFICATION_KEYS = {"guard", "verifier", "attempts", "label_source"}
PROGRESSIVE_FRACTION = 0.5  # the N events must spread over at least this much of the expected time


def get(url: str, timeout: float) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "whyball-smoke/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get("Content-Type", ""), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), ""


def read_events(url: str, count: int, timeout: float) -> list[tuple[float, dict]]:
    """First `count` match_event records of an SSE stream with their arrival time (s since the request)."""
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream", "User-Agent": "whyball-smoke/1"})
    start = time.monotonic()
    out: list[tuple[float, dict]] = []
    name = None
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name == "match_event":
                out.append((time.monotonic() - start, json.loads(line[6:])))
                if len(out) >= count:
                    break
            elif name == "end":
                break
    return out


def count_events(url: str, timeout: float) -> dict[str, int]:
    """Every SSE event name of a whole replay with how often it occurs (use speed=0: no waiting)."""
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream", "User-Agent": "whyball-smoke/1"})
    counts: dict[str, int] = {}
    with urllib.request.urlopen(req, timeout=timeout) as r:
        for raw in r:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("event: "):
                name = line[7:]
                counts[name] = counts.get(name, 0) + 1
                if name == "end":
                    break
    return counts


def wait_ready(base: str, seconds: float, timeout: float) -> tuple[bool, str]:
    """Retry /healthz once a second for up to `seconds`; any connection error or non-200 means not ready yet."""
    start = time.monotonic()
    last = "no attempt"
    while True:
        try:
            status, _, _ = get(f"{base}/healthz", min(timeout, 5.0))
            if status == 200:
                return True, f"ready after {time.monotonic() - start:.1f}s"
            last = f"HTTP {status}"
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
        if time.monotonic() - start >= seconds:
            return False, f"not ready after {seconds:g}s (last: {last})"
        time.sleep(1.0)


def run(base: str, events: int = 8, speed: float = 30.0, timeout: float = 30.0,
        wait: float = 0.0) -> list[tuple[bool, str, str]]:
    base = base.rstrip("/")
    results: list[tuple[bool, str, str]] = []
    if wait > 0:
        ok, detail = wait_ready(base, wait, timeout)
        results.append((ok, "wait", detail))
        if not ok:
            return results

    def check(ok: bool, name: str, detail: str) -> None:
        results.append((ok, name, detail))

    t0 = time.monotonic()
    match_id = None
    try:
        status, _, body = get(f"{base}/healthz", timeout)
        data = json.loads(body) if status == 200 else {}
        check(status == 200 and data.get("ok") is True, "healthz", f"HTTP {status} {body.strip()[:80]}")

        status, _, body = get(f"{base}/api/matches", timeout)
        matches = json.loads(body) if status == 200 else []
        check(status == 200 and len(matches) == EXPECTED_MATCHES, "matches",
              f"HTTP {status}, {len(matches)} matches (expected {EXPECTED_MATCHES})")
        match_id = matches[0]["id"] if matches else None

        if match_id:
            status, ctype, body = get(f"{base}/match/{match_id}", timeout)
            check(status == 200 and ctype.startswith("text/html") and 'id="root"' in body, "deep-link",
                  f"HTTP {status} {ctype} /match/{match_id}")

            url = f"{base}/api/matches/{match_id}/replay?speed={speed:g}"
            got = read_events(url, events, timeout)
            check(len(got) >= events, "sse-events", f"{len(got)} of {events} events")
            if len(got) >= events:
                first, last = got[0][0], got[-1][0]
                match_span = got[-1][1]["t"] - got[0][1]["t"]
                expected = match_span / speed
                ok = expected > 0 and (last - first) >= PROGRESSIVE_FRACTION * expected
                check(ok, "sse-progressive",
                      f"first event after {first:.2f}s, event {events} after {last:.2f}s "
                      f"(spread {last - first:.2f}s, expected about {expected:.2f}s)")

        # P2: the stored agent trace is replayed and every card says what checked it
        if TRACE_MATCH in {m["id"] for m in matches}:
            counts = count_events(f"{base}/api/matches/{TRACE_MATCH}/replay?speed=0", timeout)
            check(counts.get("trace", 0) >= 1, "trace-sse", f"{counts.get('trace', 0)} trace events in {TRACE_MATCH}")
            status, _, body = get(f"{base}/api/matches/{TRACE_MATCH}/moments", timeout)
            cards = json.loads(body) if status == 200 else []
            bad = [c.get("id") for c in cards if not isinstance(c.get("verification"), dict)
                   or set(c["verification"]) != VERIFICATION_KEYS]
            check(status == 200 and bool(cards) and not bad, "verification",
                  f"HTTP {status}, {len(cards)} cards, {len(bad)} without a verification field")
        else:
            check(False, "trace-sse", f"{TRACE_MATCH} is not among the matches")
            check(False, "verification", f"{TRACE_MATCH} is not among the matches")
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
        check(False, "request", f"{type(e).__name__}: {e}")
    check(True, "total-time", f"{time.monotonic() - t0:.1f}s")
    return results


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("url", help="base URL, e.g. https://<app-fqdn> or http://127.0.0.1:8000")
    p.add_argument("--events", type=int, default=8, help="events to read from the SSE stream")
    p.add_argument("--speed", type=float, default=30.0, help="replay speed (match seconds per second)")
    p.add_argument("--timeout", type=float, default=30.0, help="seconds to wait for any single read")
    p.add_argument("--wait", type=float, default=0.0, help="seconds to wait for /healthz before testing (default 0)")
    a = p.parse_args(argv)
    results = run(a.url, a.events, a.speed, a.timeout, a.wait)
    for ok, name, detail in results:
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    failed = [n for ok, n, _ in results if not ok]
    print(f"{'FAILED: ' + ', '.join(failed) if failed else 'ALL PASSED'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
