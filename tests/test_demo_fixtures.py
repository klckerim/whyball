import hashlib

import pytest

from app.generator import generate_match, to_jsonl
from app.generator import freeze

REGEN_HINT = (
    "üretici değişti, fixture'ları bilerek yeniden üretmek için "
    "python -m app.generator.freeze çalıştır"
)
CASES = freeze.demo_paths()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.mark.parametrize("scenario,seed,path", CASES, ids=[p.name for _, _, p in CASES])
def test_fixture_matches_generator(scenario, seed, path):
    expected = _sha256(to_jsonl(generate_match(seed, scenario)).encode("utf-8"))
    if not path.exists():
        pytest.fail(f"{REGEN_HINT} ({path.name} bulunamadı)")
    actual = _sha256(path.read_bytes())
    assert actual == expected, (
        f"{REGEN_HINT} ({path.name}: repo {actual[:12]}, üretici {expected[:12]})"
    )


def test_freeze_writes_identical_bytes(tmp_path):
    assert freeze.main(["--out-dir", str(tmp_path)]) == 0
    for _, _, path in CASES:
        assert (tmp_path / path.name).read_bytes() == path.read_bytes(), REGEN_HINT
