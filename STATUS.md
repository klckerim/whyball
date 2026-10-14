# STATUS

Updated 2026-10-14. Project rules and commands: [CLAUDE.md](CLAUDE.md). UI v2: [UI_SPEC](docs/UI_SPEC.md), [DESIGN](docs/DESIGN.md).

## Frozen
- Scope freeze: evening of 24 October. No new features after that (CLAUDE.md).
- Synthetic seeded data only; fixtures change only via `app.generator.freeze` ([datasheet](docs/DATASHEET.md)).
- LLM only in the Explain stage; unverified sentences are never published (max 2 retries, then template).
- API response shapes: only additive changes (evidence `x`/`y`; U0: timeline `x`/`y`, `squads`, new endpoints).

## Done
- Generator, analytics and moment detector, selector, claim verifier, template narrator, lint, cache.
- Foundry narrator foundry-v2 → v5.2 (claim menu); 3 live runs, 0/45 fallbacks ([LLM_RUN](docs/LLM_RUN.md)).
- Injection eval across v2–v5.2 ([EVAL](docs/EVAL.md)); human review labels in `docs/human_review*.csv`.
- Publication store replays the last run ([DEMO_NARRATION](docs/DEMO_NARRATION.md)).
- FastAPI: matches, moments, SSE replay, serves the built UI; old web UI (still the shipped one).
- Repo hygiene: README skeleton, CI workflow (pytest, Vitest + build, gitleaks), this file.
- U0 (UI v2 foundation, no screens): UI_SPEC + DESIGN log; `/healthz`, `/api/metrics`, timeline `x`/`y`,
  `squads`; OpenAPI → `web/src/api/schema.gen.ts` + drift checks; `web/test-fixtures/` from the real API;
  `<Fact>` + T1/T2 tests; `web/src/design/tokens.css` (light/dark, stage always dark); fonts; Radix.

## In progress
- 8 U0 commits on `master`, not pushed. Last CI state unknown here (GitHub API unreachable from this machine).
- Branches: `master` only, no stash. Tag `llm-baseline-v2` is on origin.

## Next
- Push U0; confirm CI (new web steps: `npm ci --prefix tools/openapi-gen`, `npm run check:api`).
- U1: shell + On Air stage on the new tokens/fonts/Fact; backend B2 (series endpoint).
- Verifier gaps listed in EVAL (below). Decide before the freeze: fix or document.
- Deploy (see Deploy state).

## Decisions (with reason)
- CI pins actions to commit SHAs, Node 24 LTS: tags can move, and 24 meets the web engines range.
- gitleaks-action without a license key: required only for organization repos; this repo is personal.
- Claim menu (v5): the model picks menu ids, code builds the numbers, so numbers cannot drift.
- Replays use the stored publication, no live model call: demo is deterministic and free.
- UI v2 decisions (themes, safe areas, fonts, Radix, Fact contract) are logged with sources in DESIGN.md.
- openapi-typescript runs from `web/tools/openapi-gen` (own lockfile, TS 5.9.3): it needs the TS 5 JS
  API, the app is on TS 7 (DESIGN D10).
- Metric definitions are written in code next to the labels (`app/explain/labels.py`), numbers from config.
- Old UI colours stay in `web/src/tokens.css`; new UI colours only in `web/src/design/tokens.css`.

## Open risks / known limits
- Verifier misses (foundry-v5.2, [EVAL](docs/EVAL.md)): `wrong_slot_binding` 0% caught,
  `role_reversed` 69.0%, `event_wrong_claim` 71.6%. Qualitative claims inside a grounded sentence pass.
- Eval and run samples are small (15 moments per run, 3 runs); one data point per prompt version.
- Stored card red_card_swing 90+1' mentions an 84' goal that none of its claims cover.
- Tests (2026-10-14, clean `npm ci`): pytest 598 passed, Vitest 333 passed, `npm run smoke` 3 passed.
- U0 close-out: metric definitions fixed (4); FastAPI/Starlette/Pydantic pinned; names ASCII; history: no endpoint/UUID.
- After `app.publish`, rerun `python -m app.api.fixtures` (pytest fails until then, by design).
- Two of the three demo matches share one run id and one prompt version.
- `.env.example` is tracked on purpose and matches the `\.env` hygiene grep; not opened (deny rule).

## Deploy state
- Target: Azure Container Apps, one container (API + built UI). `/healthz` exists (U0).
- CI (`.github/workflows/ci.yml`) tests and scans only. Not started: no Dockerfile, no infra files.
- Needs `web/dist` built before the image; keys stay in `.env`, never committed.

## Commands
Full list in [CLAUDE.md](CLAUDE.md). Daily ones:
- Test: `.venv/bin/pytest -q` and `cd web && npm test`
- Run: `.venv/bin/uvicorn app.api.main:app --reload` (UI from `web/dist`)

## Mentor summary
- Done: U0 foundation in 8 commits, no screens. English UI spec, plus a design log with checked sources
  (EBU R 095 v1.1: 5 % / 3.5 %; WCAG 2.2 SC 2.3.1).
- Backend (additive only): timeline x/y, `/api/metrics` with label/definition/window, squads, `/healthz`.
- API types generated from OpenAPI; drift fails in pytest (JSON) and in CI (`check:api`, TS).
- Fixtures are built by a script from the real API and checked by hash in both pytest and Vitest.
- `<Fact>`: T2 checked on every real claim and evidence event; T1 scan parses TSX (allow-list empty).
- Tokens: spec colours passed AA in both themes unchanged; stage tokens stay dark in both themes.
- Fonts (OFL 1.1) and Radix (MIT) licences checked in the installed packages; no TODO(verify) left.
- Tests: pytest 598 (+14), Vitest 333 (+228, mostly one test per real claim), smoke 3; clean `npm ci`.
- Deviation 1: openapi-typescript needs TS 5, so it runs from an isolated tool package (your choice).
- Deviation 2: the step-5 commit alone fails the old colour test (a `#127` in a comment; a cached run
  hid it); step 6 fixes it. CI only tests the pushed head.
- Risk closed: fastapi 0.143.0, starlette 1.7.0, pydantic 2.14.1 pinned for the OpenAPI drift test.
- Next: push and check CI, then U1 (shell + On Air stage, B2 series endpoint).
