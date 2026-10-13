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
- Publication store (no model call; replays the last run's drafts through the current pipeline): .venv/bin/python -m app.publish [--check] → data/demo_narration/{match_id}.json + docs/DEMO_NARRATION.md (diff report); rerun after any change to the explain stage, the analytics or docs/LLM_RUN.json
- API + built UI (one process): .venv/bin/uvicorn app.api.main:app --reload → /api/matches, /api/matches/{id}, /moments, /replay?speed=60&from_t=0 (SSE); WHYBALL_DATA_DIR, WHYBALL_STATIC_DIR (default web/dist)
- Foundry connection test: az login; .venv/bin/pip install -e ".[llm]"; .venv/bin/python -m app.llm.hello

## Scope freeze: evening of 24 October. No new features after that.
