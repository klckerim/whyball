# STATUS

Updated 2026-10-14. Project rules and commands: [CLAUDE.md](CLAUDE.md).

## Frozen
- Scope freeze: evening of 24 October. No new features after that (CLAUDE.md).
- Synthetic seeded data only; fixtures change only via `app.generator.freeze` ([datasheet](docs/DATASHEET.md)).
- LLM only in the Explain stage; unverified sentences are never published (max 2 retries, then template).
- API response shapes: only additive changes (the UI polish added evidence `x`/`y`).

## Done
- Generator, analytics and moment detector, selector, claim verifier, template narrator, lint, cache.
- Foundry narrator foundry-v2 → v5.2 (claim menu); 3 live runs, 0/45 fallbacks ([LLM_RUN](docs/LLM_RUN.md)).
- Injection eval across v2–v5.2 ([EVAL](docs/EVAL.md)); human review labels in `docs/human_review*.csv`.
- Publication store replays the last run ([DEMO_NARRATION](docs/DEMO_NARRATION.md)).
- FastAPI: matches, moments, SSE replay, serves the built UI.
- Web UI: scoreboard, timeline, cards, evidence panel with pitch, bottom sheet, token-based light/dark theme.
- Repo hygiene: README skeleton, CI workflow (pytest, Vitest + build, gitleaks), this file.

## In progress
- CI fix committed (openai in the dev extra), not pushed yet; needs a green python job.
- Branches: `master` only, no stash. Tag `llm-baseline-v2` is on origin.

## Next
- Real Agent trace: the store carries no trace yet, so that tab shows its empty state.
- Verifier gaps listed in EVAL (below). Decide before the freeze: fix or document.
- Push the CI fix and confirm the python job is green on 3.12.
- Deploy (see Deploy state).

## Decisions (with reason)
- CI pins actions to commit SHAs, Node 24 LTS: tags can move, and 24 meets the web engines range.
- gitleaks-action without a license key: required only for organization repos; this repo is personal.
- Claim menu (v5): the model picks menu ids, code builds the numbers, so numbers cannot drift.
- Replays use the stored publication, no live model call: demo is deterministic and free.
- UI opens at full time: a first view with all cards beats an empty kickoff screen.
- Evidence `x`/`y` added in the API, not the store: no republish, no docs churn.
- Only featured cards (llm + selected) by default: template cards are noise at first glance.
- All colours live in `web/src/tokens.css`; a test blocks literals elsewhere and checks AA contrast.
- UI value marking in card text is a heuristic: the store keeps no slot spans.

## Open risks / known limits
- Verifier misses (foundry-v5.2, [EVAL](docs/EVAL.md)): `wrong_slot_binding` 0% caught,
  `role_reversed` 69.0%, `event_wrong_claim` 71.6%. Qualitative claims inside a grounded sentence pass.
- Eval and run samples are small (15 moments per run, 3 runs); one data point per prompt version.
- Seen in a stored card: the red_card_swing 90+1' text mentions an 84' goal that none of its claims cover.
- Card-text value marking can miss a claim; it is then still listed in the evidence panel.
- Tests: pytest 584 passed, Vitest 105 passed (2026-10-14); `npm run smoke` 3 passed (2026-10-13).
- Two of the three demo matches share one run id and one prompt version.
- First CI run (2026-10-14): web and gitleaks green, python failed at collection (openai only
  in the llm extra). Fixed; a clean dev-only venv passes, but on 3.14: 3.12 not checked locally.
- `.env.example` is tracked on purpose and matches the `\.env` hygiene grep; not opened (deny rule).

## Deploy state
- Target: Azure Container Apps, one container (API + built UI).
- CI workflow in `.github/workflows/ci.yml` (tests and scan only, no deploy step).
- Not started: no Dockerfile, no infra files.
- Needs `web/dist` built before the image; keys stay in `.env`, never committed.

## Commands
Full list in [CLAUDE.md](CLAUDE.md). Daily ones:
- Test: `.venv/bin/pytest -q` and `cd web && npm test`
- Run: `.venv/bin/uvicorn app.api.main:app --reload` (UI from `web/dist`)
- UI build and smoke: `cd web && npm run build` / `npm run smoke`
- Eval: `.venv/bin/python -m eval.inject --quick`
- Store refresh after Explain changes: `.venv/bin/python -m app.publish`

## Mentor summary
- Goal: football narrator where every published sentence passes a deterministic claim verifier.
- Last task: first CI run failed; fixed the python job. P0 hygiene (4 commits) is pushed.
- P0 delivered: tracked STATUS.md, README skeleton, CI with SHA-pinned actions.
- Repo checks clean: no build output tracked, `.env.example` tracked on purpose, tag on origin.
- CI run 1: gitleaks found no secrets in the full history; web job green.
- python job failed: two test modules import openai, which only the llm extra installed.
- Fix: openai added to the dev extra; no app code or test change; tests not skipped.
- Proof: clean venv with only .[dev] passes 584 tests (Python 3.14; 3.12 not available here).
- Risk: the 3.12 job may hit a new issue past collection; known only after the push.
- Main product risk unchanged: three verifier gap types in EVAL.
- Ask for the mentor: once CI is green, close verifier gaps or document them before the freeze?
