import subprocess
import sys
import types
from pathlib import Path

import pytest

from app import serve, telemetry

ENV = telemetry.CONNECTION_STRING_ENV
REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def fake_distro(monkeypatch):
    calls = []
    mod = types.ModuleType("microsoft.opentelemetry")
    mod.use_microsoft_opentelemetry = lambda **kw: calls.append(kw)
    monkeypatch.setitem(sys.modules, "microsoft", types.ModuleType("microsoft"))
    monkeypatch.setitem(sys.modules, "microsoft.opentelemetry", mod)
    return calls


@pytest.mark.parametrize("value", [None, ""])
def test_no_connection_string_is_a_full_noop(monkeypatch, fake_distro, value):
    monkeypatch.delenv(ENV, raising=False)
    if value is not None:
        monkeypatch.setenv(ENV, value)
    assert telemetry.setup() is False
    assert fake_distro == []


def test_connection_string_turns_on_traces_only(monkeypatch, fake_distro):
    monkeypatch.setenv(ENV, "InstrumentationKey=00000000-0000-0000-0000-000000000000")
    assert telemetry.setup() is True
    assert fake_distro == [{"enable_azure_monitor": True, "disable_logging": True, "disable_metrics": True}]


def test_missing_package_keeps_telemetry_off(monkeypatch, capsys):
    monkeypatch.setenv(ENV, "InstrumentationKey=00000000-0000-0000-0000-000000000000")
    monkeypatch.setitem(sys.modules, "microsoft.opentelemetry", None)  # the import raises ImportError
    assert telemetry.setup() is False
    assert "telemetry stays off" in capsys.readouterr().err


def test_serve_sets_up_telemetry_before_starting_uvicorn(monkeypatch):
    order = []
    fake = types.ModuleType("uvicorn")
    fake.run = lambda *a, **kw: order.append("uvicorn")
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    monkeypatch.setattr(serve, "publish_check", lambda argv: 0)
    monkeypatch.setattr(telemetry, "setup", lambda: order.append("telemetry"))
    serve.main()
    assert order == ["telemetry", "uvicorn"]


def test_failed_check_never_sets_up_telemetry(monkeypatch):
    called = []
    monkeypatch.setattr(serve, "publish_check", lambda argv: 1)
    monkeypatch.setattr(telemetry, "setup", lambda: called.append(1))
    assert serve.main() == 1 and called == []


def test_noop_imports_nothing_in_a_fresh_interpreter():
    code = (
        "import sys\n"
        "from app import telemetry\n"
        "assert telemetry.setup() is False\n"
        "bad = sorted(m for m in sys.modules if m.split('.')[0] in {'microsoft', 'opentelemetry', 'azure'})\n"
        "print(bad); raise SystemExit(1 if bad else 0)\n"
    )
    env = {k: v for k, v in __import__("os").environ.items() if k != ENV}
    r = subprocess.run([sys.executable, "-c", code], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
