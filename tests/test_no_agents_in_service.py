"""The live service never runs a model or an agent: nothing it imports reaches `app.agents`, the Agent Framework or the
model client, and the image is built without them. (tests/test_api_surface.py freezes the routes; this freezes the code.)
Agent runs are an offline step: `python -m app.agents.run` writes a run file, `python -m app.publish` stores it, the
service replays the stored trace."""

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# app.explain.llm_narrator is allowed: the publication store reads its PROMPT_VERSION, and it imports the model SDK
# only inside `FoundryChatClientAdapter` when one is constructed (never at import, never by the service).
FORBIDDEN = ("app.agents", "agent_framework", "app.llm", "openai", "azure.identity", "azure.ai")
SERVICE = [*sorted((REPO / "app" / "api").glob("*.py")), *sorted((REPO / "app" / "publish").glob("*.py")),
           REPO / "app" / "serve.py", REPO / "app" / "telemetry.py"]


def _imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level:  # a relative import stays inside the package
                continue
            out.add(node.module or "")
        elif isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
    return out


def test_service_modules_do_not_import_agents_or_a_model_client():
    assert len(SERVICE) > 10
    bad = {p.name: sorted(m for m in _imports(p) if m.startswith(FORBIDDEN)) for p in SERVICE}
    assert {k: v for k, v in bad.items() if v} == {}


def test_starting_the_service_imports_no_agent_code():
    code = (
        "import sys\n"
        "import app.api.main, app.publish, app.serve, app.telemetry\n"
        "app.api.main.create_app()\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('agent_framework', 'openai') "
        "or m.startswith(('app.agents', 'app.llm', 'azure.identity', 'azure.ai')))\n"
        "print(','.join(bad)); sys.exit(1 if bad else 0)\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, f"modules loaded by the service: {r.stdout.strip()} {r.stderr[-300:]}"


def test_the_image_installs_no_agent_extra():
    dockerfile = (REPO / "Dockerfile").read_text(encoding="utf-8")
    installs = [line for line in dockerfile.splitlines() if "pip install" in line]
    assert installs and not any("llm" in line or "agent" in line or "[dev" in line for line in installs)


def test_agent_code_is_not_imported_by_anything_but_itself_and_the_tests():
    me = REPO / "app" / "agents"
    for path in (REPO / "app").rglob("*.py"):
        if me in path.parents:
            continue
        assert not {m for m in _imports(path) if m.startswith("app.agents")}, path
