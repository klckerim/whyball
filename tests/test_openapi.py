from app.api import openapi


def test_committed_schema_is_current():
    # Python-side drift check: web/openapi.json must match the app (web/src/api/schema.gen.ts is
    # generated from that file; `npm run check:api` checks the TypeScript side).
    assert openapi.OPENAPI_PATH.read_text(encoding="utf-8") == openapi.render(), (
        "run: .venv/bin/python -m app.api.openapi && cd web && npm run gen:api"
    )


def test_check_flags_a_stale_file(tmp_path):
    out = tmp_path / "openapi.json"
    assert openapi.main(["--check", "--out", str(out)]) == 1
    assert openapi.main(["--out", str(out)]) == 0
    assert openapi.main(["--check", "--out", str(out)]) == 0
    out.write_text(out.read_text(encoding="utf-8").replace('"WhyBall"', '"Other"'), encoding="utf-8")
    assert openapi.main(["--check", "--out", str(out)]) == 1


def test_schema_has_the_new_endpoints():
    paths = set(openapi.json.loads(openapi.render())["paths"])
    assert {"/healthz", "/api/metrics", "/api/matches/{match_id}"} <= paths
