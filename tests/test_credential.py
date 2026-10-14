import sys
import types

import pytest

from app.explain import credential, llm_narrator


class FakeDefault:
    created = 0

    def __init__(self):
        type(self).created += 1


@pytest.fixture
def fake_identity(monkeypatch):
    FakeDefault.created = 0
    mod = types.ModuleType("azure.identity")
    mod.DefaultAzureCredential = FakeDefault
    # AzureCliCredential is deliberately absent: nothing may reach for it any more.
    monkeypatch.setitem(sys.modules, "azure.identity", mod)
    monkeypatch.setitem(sys.modules, "azure", types.ModuleType("azure"))
    return mod


def test_make_credential_is_default_azure_credential(fake_identity):
    cred = credential.make_credential()
    assert isinstance(cred, FakeDefault) and FakeDefault.created == 1


def test_missing_identity_package_gives_the_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "azure.identity", None)  # makes the import raise ImportError
    with pytest.raises(ImportError, match="azure-identity"):
        credential.make_credential()


def test_foundry_narrator_builder_uses_the_credential_chain(fake_identity, monkeypatch):
    seen = {}

    class FakeAdapter:
        def __init__(self, **kw):
            seen.update(kw)

    dotenv = types.ModuleType("dotenv")
    dotenv.load_dotenv = lambda *a, **kw: None  # the test must not read a local .env
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)
    monkeypatch.setattr(llm_narrator, "FoundryChatClientAdapter", FakeAdapter)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.invalid/api/projects/x")
    monkeypatch.setenv("FOUNDRY_MODEL", "m")
    llm_narrator.foundry_narrator_from_env([])
    assert isinstance(seen["credential"], FakeDefault)
