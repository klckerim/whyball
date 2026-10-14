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

## In progress
- P0 repo hygiene: STATUS.md, CI workflow, README skeleton, repo checks. No code behaviour change.
- Branches: `master` only (local and origin).

## Next
- Real Agent trace: the store carries no trace yet, so that tab shows its empty state.
- Verifier gaps listed in EVAL (below). Decide before the freeze: fix or document.
- Deploy (see Deploy state).

## Decisions (with reason)
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

## Deploy state
- Target: Azure Container Apps, one container (API + built UI).
- Not started in the repo: no Dockerfile, no infra files, no CI workflow.
- Needs `web/dist` built before the image; keys stay in `.env`, never committed.

## Commands
Full list in [CLAUDE.md](CLAUDE.md). Daily ones:
- Test: `.venv/bin/pytest -q` and `cd web && npm test`
- Run: `.venv/bin/uvicorn app.api.main:app --reload` (UI from `web/dist`)
- UI build and smoke: `cd web && npm run build` / `npm run smoke`
- Eval: `.venv/bin/python -m eval.inject --quick`
- Store refresh after Explain changes: `.venv/bin/python -m app.publish`

## Mentor summary
- Goal: multi-agent football narrator where every sentence is checked against deterministic metrics.
- Where it stands: pipeline, eval, API and a polished replay UI are done and committed on master.
- Last task: UI polish. Full-time opening, evidence panel with pitch, timeline markers, theme tokens.
- Backend change: only additive `x`/`y` on evidence events, with a test.
- Quality: all suites green; before/after screenshots at 1440, 1024 and 390 px, light and dark.
- Main risk: three verifier gap types in EVAL; the demo does not hide them.
- Data finding: one stored card has a sentence its claims do not cover.
- Not done: deployment files and live agent traces.
- Ask for the mentor: is it better to close verifier gaps or to document them before the freeze?
