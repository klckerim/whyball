# WhyBall

WhyBall narrates synthetic football matches and publishes a sentence only if its claims pass a deterministic verifier.

**Status: WIP.** Current state, decisions and known limits: [STATUS.md](STATUS.md).

## What it does

- A seeded generator builds synthetic matches (no real clubs or players; see [docs/DATASHEET.md](docs/DATASHEET.md)).
- Analytics and a moment detector compute metrics and key moments. No LLM is used here.
- The explain stage writes one card per moment. A template narrator works offline; an optional LLM narrator only picks from a menu of claims that code has already built and verified.
- Every draft goes through lint and claim verification. A draft that fails is retried at most twice, then replaced by the template text.
- A FastAPI app serves the matches, the moments, an SSE replay and the built web UI (Vite + React + TS).

How well the verifier catches injected errors, including the types it misses: [docs/EVAL.md](docs/EVAL.md).

## Setup

Requires Python 3.12+ and Node 22.22+, 24.15+ or 26+.

```sh
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
cd web && npm ci && npm run build && cd ..
.venv/bin/uvicorn app.api.main:app --reload   # http://127.0.0.1:8000
```

The LLM narrator is optional and needs its own extra and credentials; see [CLAUDE.md](CLAUDE.md) and `.env.example`. Keys go in `.env`, which is never committed.

## Test

```sh
.venv/bin/pytest -q
cd web && npm test && npm run build
```

CI runs the same checks plus a gitleaks secret scan: [.github/workflows/ci.yml](.github/workflows/ci.yml).

## License

[MIT](LICENSE)
