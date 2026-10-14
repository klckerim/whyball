# WhyBall
Multi-agent football match narrator. Every claim is verified against deterministic metrics.

## Stack
Python + FastAPI, Vite + React + TS, SQLite, Azure Container Apps.

## Rules
- LLM only in the Explain stage. Analytics and the moment detector do not use an LLM.
- A sentence that does not pass the Verifier is never published. Max 2 retries, then the template fallback.
- Data is synthetic and seeded. No real club or player names.
- Never commit secrets. Keys live in .env.
- Tests must pass after every change.

## Commands
- Setup: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
- Test: .venv/bin/pytest -q
- Generate a match: .venv/bin/python -m app.generator --seed 42 [--scenario late_comeback|red_card_swing|dominant_loss] [--out match.jsonl]
- Regenerate fixtures: .venv/bin/python -m app.generator.freeze (only if the generator changed on purpose; then update the table in docs/DATASHEET.md)
- Moments: .venv/bin/python -m app.analytics --scenario red_card_swing --seed 42 [--jsonl] (or --input data/demo/<file>.jsonl)
- Narration + verification: .venv/bin/python -m app.explain --input data/demo/red_card_swing_seed42.jsonl [--lang en] [--all]
- Narration pipeline: .venv/bin/python -m app.explain.run --input data/demo/<file>.jsonl --narrator template|fake:<mode> [--lang en] [--no-cache] (cache: data/cache/, not tracked by git)
- Injection evaluation (foundry-v2 free text ↔ v3 slot ↔ v4 slot + {event:} + strict lint ↔ v4.1 event type allow-list + player repeat + pronoun/article ↔ v5 claim menu): .venv/bin/python -m eval.inject [--quick] (rewrites docs/EVAL.md; reads the v3 human labels from docs/human_review.foundry-v3.csv)
- LLM narrator (optional): .venv/bin/pip install -e ".[llm]"; az login; FOUNDRY_PROJECT_ENDPOINT and FOUNDRY_MODEL in .env (see .env.example); --narrator foundry (at most 60 calls per run; foundry-v5: app/explain/menu.py builds the claims, the model only uses menu ids)
- Real LLM measurement (3 demo matches, spends tokens): .venv/bin/python -m eval.llm_run --lang en [--repeat 3] → docs/LLM_RUN.json (rejected drafts included), docs/LLM_RUN.md, docs/human_review.csv (from the last run; never overwritten if filled in by hand); re-render only: --from-json docs/LLM_RUN.json. Earlier versions are archived as docs/LLM_RUN.foundry-v*.json (the comparison table reads them)
- Publication store (no model call; replays the last run's drafts through the current pipeline): .venv/bin/python -m app.publish [--check] → data/demo_narration/{match_id}.json + docs/DEMO_NARRATION.md (diff report); rerun after any change to the explain stage, the analytics or docs/LLM_RUN.json; then rebuild the web test fixtures
- API + built UI (one process): .venv/bin/uvicorn app.api.main:app --reload → /api/matches, /api/matches/{id}, /moments, /events, /series?metric=pressure_balance&step=60, /replay?speed=60&from_t=0 (SSE), /api/metrics, /healthz; page paths without a file get index.html (deep links); WHYBALL_DATA_DIR, WHYBALL_STATIC_DIR (default web/dist)
- Web UI (Vite + React + TS, web/): cd web && npm ci; npm run dev (proxies /api to :8000) | npm run build (→ web/dist, served by the API) | npm test (Vitest) | npm run smoke (build + tests/test_smoke_e2e.py against the real build)
- Web test fixtures (from the real API over data/demo_narration; rerun after app.publish or an API response change): .venv/bin/python -m app.api.fixtures [--check] → web/test-fixtures/ (+ manifest.json hashes)
- API types (after an API model change): .venv/bin/python -m app.api.openapi (→ web/openapi.json; --check in pytest), then cd web && npm ci --prefix tools/openapi-gen && npm run gen:api (→ web/src/api/schema.gen.ts; npm run check:api in CI)
- UI screenshots (review, not tests; uses the installed Google Chrome, no browser download): cd web && npm run build && npm ci --prefix tools/shots && node tools/shots/shots.mjs [out-dir] (default notes/shots/u2, untracked; four shots: On Air, Proof dark, Proof light 1920, Proof 390)
- Container (see docs/DEPLOY.md; the user runs every `az` command): docker build -t whyball . && docker run -p 8000:8000 whyball (entry `python -m app.serve`, starts only if `app.publish --check` passes); remote smoke: python3 scripts/smoke_remote.py <url>; deploy constraints: deploy/constraints.txt; the public API surface is frozen by tests/test_api_surface.py (no request-time LLM or billable-resource endpoint)
- Foundry connection test: az login; .venv/bin/pip install -e ".[llm]"; .venv/bin/python -m app.llm.hello

At the end of every task, update STATUS.md (replace stale lines, keep it under 80 lines) and rewrite its Mentor summary section.

## Scope freeze: evening of 24 October. No new features after that.
