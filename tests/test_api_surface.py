"""Cost-abuse guard: the public API surface is frozen.

The live deployment (docs/DEPLOY.md) is public and unauthenticated. No endpoint may call a model or any
other billable Azure resource while serving a request; every endpoint reads the stored, seeded demo data.
Adding a route fails this test on purpose: review it against that rule (add authentication and a rate
limit first if it would spend money), then update the sets below.
"""

import subprocess
import sys
from pathlib import Path

from fastapi.routing import APIRoute
from starlette.routing import Mount

from app.api import openapi
from app.api.main import create_app

REPO_ROOT = Path(__file__).resolve().parents[1]

OPENAPI_OPERATIONS = {
    ("GET", "/api/health"),
    ("GET", "/api/matches"),
    ("GET", "/api/matches/{match_id}"),
    ("GET", "/api/matches/{match_id}/events"),
    ("GET", "/api/matches/{match_id}/moments"),
    ("GET", "/api/matches/{match_id}/replay"),
    ("GET", "/api/matches/{match_id}/series"),
    ("GET", "/api/metrics"),
    ("GET", "/healthz"),
}

# Everything the app routes, including what the schema leaves out: FastAPI's own docs routes and the
# static UI mount.
ALL_ROUTES = OPENAPI_OPERATIONS | {
    ("GET", "/docs"), ("GET", "/docs/oauth2-redirect"), ("GET", "/openapi.json"), ("GET", "/redoc"),
    ("MOUNT", "/"),
}


def _operations(schema):
    return {(m.upper(), path) for path, ops in schema["paths"].items() for m in ops}


def test_openapi_paths_are_frozen():
    assert _operations(openapi.json.loads(openapi.render())) == OPENAPI_OPERATIONS


def test_every_route_is_a_get_or_the_static_mount(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html>", encoding="utf-8")
    found = set()
    for route in create_app(static_dir=tmp_path).routes:
        if isinstance(route, Mount):
            found.add(("MOUNT", route.path or "/"))
        else:
            found |= {(m, route.path) for m in route.methods - {"HEAD"}}
    assert found == ALL_ROUTES
    assert not any(isinstance(r, APIRoute) and r.methods - {"GET", "HEAD"}
                   for r in create_app(static_dir=tmp_path).routes)


def test_app_never_loads_a_model_or_azure_client():
    # A fresh interpreter: importing and building the app, and answering a request, must not import any
    # model or Azure client library (they are optional extras that the image does not install).
    code = (
        "import sys, tempfile, pathlib\n"
        "from fastapi.testclient import TestClient\n"
        "from app.api.main import create_app\n"
        "d = pathlib.Path(tempfile.mkdtemp()); (d / 'index.html').write_text('x')\n"
        "with TestClient(create_app(static_dir=d)) as c:\n"
        "    assert c.get('/api/matches').status_code == 200\n"
        "    assert c.get('/healthz').status_code == 200\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in\n"
        "             {'openai', 'agent_framework', 'azure', 'anthropic'})\n"
        "print(bad)\n"
        "raise SystemExit(1 if bad else 0)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
