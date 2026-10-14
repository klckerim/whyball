import sys

import pytest

from app import serve


@pytest.fixture
def uvicorn_calls(monkeypatch):
    calls = []
    fake = type(sys)("uvicorn")
    fake.run = lambda *a, **kw: calls.append((a, kw))
    monkeypatch.setitem(sys.modules, "uvicorn", fake)
    return calls


def test_failing_check_does_not_start_the_server(monkeypatch, uvicorn_calls, capsys):
    monkeypatch.setattr(serve, "publish_check", lambda argv: 1)
    assert serve.main() == 1
    assert uvicorn_calls == []
    assert "not starting the server" in capsys.readouterr().err


def test_check_runs_in_compare_only_mode(monkeypatch, uvicorn_calls):
    seen = []
    monkeypatch.setattr(serve, "publish_check", lambda argv: seen.append(argv) or 0)
    serve.main()
    assert seen == [["--check"]]


def test_passing_check_starts_the_server_on_port_from_env(monkeypatch, uvicorn_calls):
    monkeypatch.setattr(serve, "publish_check", lambda argv: 0)
    monkeypatch.setenv("PORT", "9123")
    assert serve.main() == 0
    (args, kwargs), = uvicorn_calls
    assert args == ("app.api.main:app",) and kwargs == {"host": "0.0.0.0", "port": 9123}


def test_default_port(monkeypatch, uvicorn_calls):
    monkeypatch.setattr(serve, "publish_check", lambda argv: 0)
    monkeypatch.delenv("PORT", raising=False)
    serve.main()
    assert uvicorn_calls[0][1]["port"] == 8000


def test_real_store_passes_the_check():
    # The committed store is current (the same check the container runs before it starts).
    assert serve.publish_check(["--check"]) == 0
