# STATUS

Updated 2026-10-14. Project rules and commands: [CLAUDE.md](CLAUDE.md). UI v2: [UI_SPEC](docs/UI_SPEC.md), [DESIGN](docs/DESIGN.md).

## Frozen
- Scope freeze: evening of 24 October. No new features after that (CLAUDE.md).
- Synthetic seeded data only (fixtures change only via `app.generator.freeze`, [datasheet](docs/DATASHEET.md)).
  LLM only in the Explain stage; unverified sentences are never published (max 2 retries, then template).
- API response shapes: only additive changes (U0: timeline `x`/`y`, `squads`; U1: card `checks`, events, series; U2: card `segments`).

## Done
- Generator, analytics, moment detector, selector, claim verifier, template narrator, lint, cache.
- Foundry narrator foundry-v2 → v5.2 (claim menu); 3 live runs, 0/45 fallbacks ([LLM_RUN](docs/LLM_RUN.md)).
- Injection eval v2–v5.2 ([EVAL](docs/EVAL.md)); publication store replays the last run ([DEMO_NARRATION](docs/DEMO_NARRATION.md)).
- README, CI (pytest, Vitest + build, gitleaks, docker). FastAPI (matches, moments, events, series, SSE, `/healthz`, UI deep links).
- U0 (UI v2 foundation, no screens): UI_SPEC + DESIGN log; `/healthz`, `/api/metrics`, timeline `x`/`y`,
  `squads`; OpenAPI → `web/src/api/schema.gen.ts` + drift checks; `web/test-fixtures/` from the real API;
  `<Fact>` + T1/T2 tests; `web/src/design/tokens.css` (light/dark, stage always dark); fonts; Radix.
- U1 (7 commits): shell, routes, On Air stage, transport, timeline, pressure band; card `checks` at publish.
- U2 (9 commits): card text stored as `segments` (claim values marked by the code that writes them); Proof face
  (moment rail, Receipt with definition/window/verification record, evidence pitch + list); Flip (seal button, P);
  band caption; old UI and `/legacy` deleted. 4 screens reviewed ([DESIGN](docs/DESIGN.md) D26-D31).
- P1 (8 commits): image, start-up guard, DefaultAzureCredential, frozen API surface, remote smoke test,
  CI docker job (+ `--wait` fix), [DEPLOY](docs/DEPLOY.md), optional App Insights. Deployed 2026-10-14 (the user ran `az`):
  Sweden Central, image tag p1-20261014-1822, 0.5 vCPU / 1.0 Gi, 1-2 replicas, user-assigned identity + AcrPull,
  remote smoke test ALL PASSED. Foundry role not assigned, App Insights not enabled.
  Public address: https://whyball.happyground-485eb3be.swedencentral.azurecontainerapps.io

## In progress
- 7 U1 + 8 P1 (deployed) + P1 closure + 9 U2 commits on `master` only, not pushed; U0 and tag `llm-baseline-v2` are on origin. CI not checked here.

## Next
- Push; confirm CI. The deployed app (P1) still serves the U1 build: redeploy (DEPLOY 8.1) to publish U2.
- U3: trace tape, Rejected takes, Red pen, Method (fixtures first, real data after; the old trace panel's job).
- Verifier gaps (EVAL, below): fix or document before the freeze.

## Decisions (with reason)
- CI pins actions to commit SHAs on Node 24 LTS; gitleaks-action needs no license key (personal repo).
- Claim menu (v5): the model picks menu ids, code builds the numbers, so numbers cannot drift.
- Replays use the stored publication, no live model call: demo is deterministic and free.
- UI v2 decisions (themes, safe areas, fonts, Radix, Fact contract) are logged with sources in DESIGN.md.
- openapi-typescript runs from `web/tools/openapi-gen` (own lockfile, TS 5.9.3): it needs the TS 5 JS
  API, the app is on TS 7 (DESIGN D10).
- Stage plays fetched events with a client clock, not SSE (exact seek, fake-timer tests; DESIGN D14).
- Seal reads the card's `checks` and says "Checked by code": no Verifier agent exists (D21, D28).
- Segments come from the code that writes the text, never from matching the sentence (D26).

## Open risks / known limits
- Verifier misses (foundry-v5.2, [EVAL](docs/EVAL.md)): `wrong_slot_binding` 0% caught,
  `role_reversed` 69.0%, `event_wrong_claim` 71.6%. Qualitative claims inside a grounded sentence pass.
- Eval and run samples are small (15 moments per run, 3 runs).
- Stored card red_card_swing 90+1' mentions an 84' goal that none of its claims cover.
- Tests (2026-10-14, uncached): pytest 672, Vitest 396 (old UI's 104 gone with it), `npm run smoke` 7; initial JS 113.6 KB gzip.
- Minutes, names and event phrases inside a card sentence are plain text, not `<Fact>` (D26).
- 390 px: stage pitch is small, close timeline glyphs overlap near full time (U5).
- After `app.publish`: rerun `app.api.fixtures` (pytest fails until then, by design).
- Two demo matches share one run id and prompt version. `.env.example` is tracked; never opened.

## Deploy state
- Azure Container Apps, one container, Sweden Central ([DEPLOY](docs/DEPLOY.md)).
- Image: digest-pinned, non-root; `python -m app.serve` refuses to start if `app.publish --check` fails; CI scans it.
- Public, no endpoint calls a model or billable resource (`tests/test_api_surface.py`). Checks: local image smoke (U2 build) and the Azure smoke (P1 build) ALL PASSED.

## Mentor summary
- Commits (U2): 6f34e8c P1 closure · aae49f7 explain parts · 86cb9da segments in store/API/fixtures · 975c4bc Fact sources
  + SentenceText · e88edf8 Proof · 9d54c1b Flip · c91cfe6 band caption · ba7457a review fixes · c18b078 old UI deleted · docs.
- Tests: pytest 672 (+27), Vitest 396 (500 before the old UI went), smoke 7; JS 113.6 KB gzip (budget 250).
- `provenance.allow.ts` additions: 0. Unplaceable claims: 0 of 90 (74 in the sentence, 16 stated in words:
  goals 8, score_margin 5, red_cards 2, penalties_saved 1: a count of 1 or a margin is worded, not numbered).
- Dropped old features: trace panel (U3), Evidence/Trace tabs and bottom sheet, EventSource replay hook, crests,
  `markClaims`, featured/all filter, claim chips + hover preview, old timeline bar and pitch.
- Deviations: seal reads "Checked by code" (was "Verified"); Fact got claim-field, window and checks sources (D28);
  proof uses plain divs for the faces (no Radix `Tabs.Content`, so the old face stays for the turn); stage height
  allowance 290 to 320 px for the band caption.
- TODO(verify): none added. Slips: two commits went in with `;` after a failing check (fixed by amend before moving on).
- Resembles the forbidden list: left rail is text + glyph, not an icon menu; the 56 px claim value is plain text on
  the Receipt, not a coloured tile. Nothing else (no avatars, crests, heat maps, sparkles, glass).
- Shots (untracked): notes/shots/u2/{onair-1440x900-dark,proof-1440x900-dark,proof-1920x1080-light,proof-390x844-dark}.png;
  no horizontal scroll, no console errors. Docker build + `smoke_remote.py --wait 60` on a local container: ALL PASSED.
