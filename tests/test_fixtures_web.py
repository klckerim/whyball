import json

from app.api import fixtures


def test_web_fixtures_are_current():
    # Fails after `python -m app.publish` or an API change until the fixtures are rebuilt.
    assert fixtures.main(["--check"]) == 0, f"run: {fixtures.COMMAND}"


def test_manifest_matches_the_publication_store():
    manifest = json.loads((fixtures.FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    store_dir = fixtures.REPO_ROOT / "data" / "demo_narration"
    assert manifest["sources"] == {
        f"data/demo_narration/{p.name}": fixtures._sha256(p.read_bytes()) for p in sorted(store_dir.glob("*.json"))
    }
    for name, digest in manifest["files"].items():
        assert fixtures._sha256((fixtures.FIXTURES_DIR / name).read_bytes()) == digest


def test_check_flags_a_changed_or_extra_file(tmp_path):
    assert fixtures.main(["--out", str(tmp_path)]) == 0
    assert fixtures.main(["--check", "--out", str(tmp_path)]) == 0
    (tmp_path / "extra.json").write_text("{}", encoding="utf-8")
    assert fixtures.main(["--check", "--out", str(tmp_path)]) == 1
    (tmp_path / "extra.json").unlink()
    path = tmp_path / "metrics.json"
    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    assert fixtures.main(["--check", "--out", str(tmp_path)]) == 1
