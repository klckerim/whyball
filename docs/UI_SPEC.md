# WhyBall Web UI v2: specification

Status: approved draft (2026-10-14). Source of truth for UI stages U1–U5; design decisions and their
sources live in [DESIGN.md](DESIGN.md). Tags: **[standard]** taken from a cited standard,
**[design]** our own parameter (not a standard), **[open]** not verified yet.

## 1. Summary
- The old UI is replaced. It stays in `web/src/` until the new one covers it; the API contract is kept,
  changes are **additive only**.
- Concept **On Air / Proof**: one match moment has two faces, the broadcast graphic a viewer sees (On Air)
  and the grounds for every word (Proof). One key flips between them. Not a dashboard: an **auditable
  broadcast graphic**.
- Three signature interactions, all from our own data:
  1. **Flip**: click the verified seal, the graphic turns into its evidence.
  2. **Red pen**: corrupt a sentence, see which layer catches it (and which do not).
  3. **Rejected takes**: the model's rejected drafts with their rejection reasons, from real run logs only.
- **No fabrication**: every number, name and time on screen goes through `<Fact>` (§8). What our data does
  not hold (player positions, formations, xG, heat maps, photos) is **not shown** (§4).
- We have no official league graphics style guide and do not claim one. We apply measurable broadcast
  properties instead: 16:9 output, EBU R 095 safe areas, flash limit, contrast, transparent overlay (§3).
- Personalization is a UI concern: On Air = fan, Proof = analyst; favourite team and player focus are
  deterministic filters. No extra LLM output (the text is the same for both; README states this).

## 2. Reference images: take the principle, not the layout
Five reference screenshots (dark analytics dashboards and AI-generated mockups) were reviewed for principles
only. Kept principles: jump from a moment straight to the pitch; honest "example output" labelling; a
pitch-centred one-glance story; a plain hierarchy (score on top, scoring events, stats aside); a
"why does this matter" + key evidence pairing. Several mockups contained invented numbers: exactly the
failure this product exists to prevent.

**Forbidden list (anti-references):**
- Left sidebar icon menu; three-column card/tile wall; coloured big-number stat tiles.
- Pitch with player dots, formations, heat-map blobs, avatars, crests, logos.
- "AI" sparkle badges, cyan-on-navy accents, glassmorphism.
- Any real club, player, brand or match footage; any third-party product logo.
- Copying the layout of any reference image.

## 3. Broadcast requirements
| # | Requirement | Value | Tag |
|---|---|---|---|
| B1 | Program frame 16:9, design size 1920×1080, scales | — | [design] |
| B2 | Graphics inside **graphics-safe** (5 % per edge); critical action inside **action-safe** (3.5 % per edge) | EBU R 095 v1.1 | [standard] |
| B3 | No more than **three flashes in any one second**; no strobe; transitions ≤ 400 ms | WCAG 2.2 SC 2.3.1 (Level A); 400 ms [design] | [standard] |
| B4 | Text contrast ≥ 4.5:1, non-text ≥ 3:1; meaning never by colour alone (shape + label) | WCAG AA | [standard] |
| B5 | Body text ≥ 32 px and numbers ≥ 56 px at 1080p; readable at 50 % scale | — | [design] |
| B6 | Graphic dwell `max(4 s, reading time)`, adjustable; at 300× replay a graphic still stays for its wall-clock dwell | — | [design] |
| B7 | Transparent overlay output: `/overlay`, alpha background, no scrollbars, deterministic from URL params | — | [design]; OBS compatibility not claimed [open] |
| B8 | 60 fps target, no layout shift | — | [design] |

## 4. Data-truth matrix
Sources: `docs/DATASHEET.md`, `app/publish/schema.py`, `app/analytics/metrics.py`. Event fields:
`seq, period, minute, second, type, team, player, x, y, outcome, score, data`; `x,y` is the **ball position**
(105×68, home attacks towards x=105 in both halves), null for cards, substitutions and period events.

| Feature | Needs | Have it? | Decision |
|---|---|---|---|
| Score, minute, half time | event `score`, clock | yes | show |
| Event markers on the pitch | event `x,y` | yes (null for cards/subs) | show; null → "no location" (API: B1) |
| Ball trail animation | consecutive `x,y` | yes | show; interpolation is visual only, labelled "synthetic feed visualization" |
| Shot map | `shot` `x,y` + `outcome` | yes | show |
| Possession, territorial share (`field_tilt`), shots, corners, fouls, cards | metrics | yes | show (definitions and windows from the API) |
| Pressure balance, momentum curve | metric series | yes, series endpoint pending (B2) | show; our metric, **not** xG or win probability |
| Player focus | event `player` | yes | show (§9) |
| Player positions, formation, per-player heat map | tracking data | **no** | do not show |
| Passing network | pass receiver | **no** (passer only) | do not show |
| xG, xT, win probability, player rating | a model | **no** | do not show, never invent |
| Ball/shot speed, distance run | speed data | **no** | do not show |
| Match footage, crests, photos, real names | — | **no** | forbidden |
| Career / historical stats | history | **no** | do not show |
| Agent trace, rejected drafts | agent run output | rejected drafts exist in `docs/LLM_RUN.json`; trace schema fills later | schema + fixture first, real data later |
| "Break it" examples | `eval.inject` | exportable, export script pending (B5) | U3 |
| Multiple languages | — | no | product is English |

## 5. Concept and screens
**One line:** a football broadcast graphic you can turn over to audit every word.

- **On Air:** 16:9 program frame, score bug, lower third with the verified narration, verified seal,
  a permanent "SYNTHETIC DATA" mark.
- **Proof:** the audit face of the same moment: **Receipt** (each value in the sentence → claim → window
  definition → evidence events → position on the pitch), **trace tape**, **rejected takes**, **Red pen**.
- Not a stats board: information sits around the narration, never replaces it.

**Routes:** `/` (default match, On Air) · `/match/:id` (`?mode=proof&moment=…&t=…`) · `/method` · `/overlay`.
**Top bar:** match picker · mode switch (On Air | Proof) · favourite team · Method link · SYNTHETIC DATA. No left menu.

On Air (desktop): top bar; 16:9 program stage (score bug top left, SYNTHETIC DATA top right, abstract pitch
with ball marker and short trail, lower third with type glyph, minute, sentence and seal); below it a
transport (play, speed, previous/next moment) and a timeline with type glyphs and a half-time mark.

Proof (desktop): moment rail | Receipt (sentence with underlined claim values, claim definition, window,
value, evidence count) | evidence pitch + events list; below: trace tape, Rejected takes, Red pen.

Mobile (390 px): stage on top at full width, lower-third text and transport below; Proof is a separate tab
(bottom nav: On Air · Proof · Method); evidence pitch and trace open as bottom sheets. No horizontal scroll.

**Required states on every screen:** loading (skeleton); empty (a true statement such as "no narrated
moments in this match"); error (retry; SSE resumes with `from_t`); missing data (`null` → "no location",
"no trace yet", never `0`).

**Method page:** verification pipeline diagram (SVG), measurement table **from the API** (`/api/method`,
built from `docs/EVAL.md` / `docs/LLM_RUN.json`), known limits, datasheet link, a three-step "evaluate in
90 seconds" guide.

**Overlay:** `/overlay?match=…&mode=lower-third`, transparent, fixed 1920×1080, lower third + score bug only,
driven by SSE; safe-area guides with `&guides=1`.

**Capture mode** (`?capture=1`): chrome and shortcut hints hidden, fixed 1920×1080, large type.
**Tour** (`?tour=1`): unattended flow: moment arrives → Flip → evidence → trace → Red pen → Method number.

## 6. Visual language
| Item | Decision |
|---|---|
| Theme | Dark and light. Default follows `prefers-color-scheme`; manual switch stored in `localStorage` (try/catch; session only if blocked). The **program stage stays dark in both themes** (`--stage-*` tokens): it stands for the broadcast picture. |
| Type | Display/numbers: **Barlow Condensed**; UI/body: **Inter**; both SIL OFL 1.1, self-hosted, licence text in the repo. |
| Icons | Own SVG glyph set per type (goal ●, red card ▮, penalty ◆, pressure ▲, dominance ■); no third-party icons. |
| Motion | Fade/slide ≤ 400 ms; no strobe; off under `prefers-reduced-motion`. |
| Layout | 8 px grid; content width ≤ 1440 px outside the stage. |

**Starting colours, dark** (bg `#0B0F14`, surface `#131A23`, surface-2 `#1B2430`): text `#EDF1F6`, muted
`#A3AFBF`, accent (broadcast yellow) `#FFD23F` with `#0B0F14` text on it, verified `#3DD6A0`, reject
`#FF6B6B`, src-llm `#8AB4FF`, src-fallback `#FFA94D`, home `#4DA3FF`, away `#FF8A5B`, control-border `#6B7787`.

**Starting colours, light** (bg `#F4F6FA`, surface `#FFFFFF`, surface-2 `#E9EEF5`): text `#0F1720`, muted
`#4A5565`, accent-ink (text/links) `#7A5A00`, accent (fill only, `#0B0F14` text on it) `#FFD23F`, verified
`#0B7A57`, reject `#B3261E`, src-llm `#2457C5`, src-fallback `#9A4F00`, home `#1F63C2`, away `#B8431A`,
control-border `#6B7787`.

Rules: `web/src/design/tokens.test.ts` computes every pair in both themes (text ≥ 4.5, indicators and
interactive borders ≥ 3); these are starting values and change if a test fails. Home and away are close
in luminance, so colour is never enough: circle (home) vs ring/square (away), team name label always
next to it. Decorative borders and interactive control borders are separate tokens.

## 7. Truthfulness contract
| # | Rule | Enforced by |
|---|---|---|
| T1 | Every number, name and time on screen is drawn by `<Fact>`; no numeric literal in JSX | `provenance.test.tsx` + source scan (digits in JSX banned outside an explicit allow-list) |
| T2 | `<Fact>` output carries `data-claim-id` or `data-event-id`; for every fixture card the id exists in the payload and the text equals `display` exactly | Vitest |
| T3 | TS API types are generated from the FastAPI OpenAPI schema (`openapi-typescript`); drift fails CI | CI step |
| T4 | Missing data is never drawn as 0 or an empty bar: "no data / no location / no trace yet" | component tests |
| T5 | Metric names, definitions and windows come from the API (`/api/metrics`, from code); the UI writes no definitions | API + UI tests |
| T6 | Method page numbers come from JSON; no hand-written rate or percentage in the UI | T1 scan |
| T7 | No sample or fake data in the production bundle; fixtures only in `web/test-fixtures/`, built by script from the real publication store, content hash checked | script + test |
| T8 | **SYNTHETIC DATA** mark always on the stage and the overlay; "feed visualization is synthetic" note | visual test |
| T9 | Every value taken from a standard is in `docs/DESIGN.md` with its source; no unsourced "standard" claim | review |

**Working rules for every coding session:** do not invent data, standards or licences (write
`TODO(verify)` and ask); log every design decision in `docs/DESIGN.md` with reason and source; do not copy
the reference layouts or brands (§2); check visual work in a real browser (3 screenshots before / after);
never read `.env`, never write keys, no force push, one tested commit per step.

## 8. Personalization (UI level)
| Experience | Face | Sees |
|---|---|---|
| Fan (default) | On Air | one sentence + one highlighted value, favourite team colour accent, simple controls |
| Analyst | Proof | claim table, window definitions, evidence events, trace, Red pen |

- Favourite team: its moments are highlighted / filtered; team colour accent on the stage.
- Player focus: pick a fictional player (squad from `match_meta`, API B7). Timeline filters to moments
  whose evidence includes that player; the pitch shows only their events. With no moment, say so
  ("no narrated moments") and show an **event log** (no narration, no LLM, clearly labelled).
- All deterministic filters; no extra LLM call. Honest limit: both experiences share the same text.

## 9. Front-end architecture
| Decision | Choice | Reason |
|---|---|---|
| Framework | Vite + React + TS (existing) | time, familiar |
| Routing | `react-router` | four routes |
| Accessible primitives | Radix UI (Tabs, Dialog, Tooltip, ToggleGroup, Popover), unstyled, MIT | correct keyboard/focus/ARIA without a UI-kit look |
| Style | plain CSS + `design/tokens.css` (CSS Modules) | custom visual language |
| Charts | hand-written SVG (pitch, momentum, shot map) | distinctive, small bundle |
| API types | OpenAPI → `openapi-typescript` | T3 |
| State | `useReducer` + context (replay clock, selection, mode) | no Redux needed |
| Live data | SSE hook, reconnect with `from_t` | container restarts [open] |
| Tests | Vitest + Testing Library; three browser screenshots per stage | |
| Fonts | `@fontsource/*`, self-hosted | no CDN, licence in repo |

Directories: `web/src/{app, api, design, stage, proof, breakit, method, overlay, state}` and
`web/test-fixtures/`. `design/` holds `tokens.css`, `Fact`, `Seal`, `SourceBadge`, `TypeGlyph`.
Budgets [design]: initial JS ≤ 250 KB gzip; first meaningful paint < 2.5 s (measure on deploy [open]).

### Backend additions (all additive)
| Code | Addition | Acceptance |
|---|---|---|
| B1 | Timeline events carry `x,y` (nullable) | existing fields unchanged; goal → numbers, card → null |
| B2 | `GET /api/matches/{id}/series?metric=&step=` (deterministic, from `metrics_at`) | same input, same output; definition and window in the response |
| B3 | `GET /api/metrics` (label, definition, window; from the code registry) | matches the code exactly |
| B4 | `GET /api/method` (measurement summary from JSON) | no hand-written number |
| B5 | "break-it" export from `eval` + `GET /api/break-it` (original, corrupted, class, catching layer/code) | includes misses |
| B6 | `trace` field (schema exists) filled by the agent stage | schema + fixture now |
| B7 | Squads (`match_meta`) in the match detail | for player focus |
| B8 | `GET /healthz` | shared with deploy |

## 10. Accessibility and quality gates
- Keyboard: **Space** play/pause, **P** Flip, **←/→** previous/next moment, **?** shortcut help; visible focus rings; ARIA via Radix.
- `prefers-reduced-motion`; no strobe (B3); AA contrast in **both themes**; no meaning by colour alone; theme switch keyboard-reachable and persistent.
- Widths: 390 / 768 / 1440 / 1920. No horizontal scroll.
- Lighthouse accessibility ≥ 90, no console errors [open: target, measured in U5].
- Gates: `npm test`, `pytest`, T1–T9 tests, OpenAPI type drift check, three-screenshot review.

## 11. Stages
| Stage | Content | Acceptance |
|---|---|---|
| U0 | Contract and foundation: this file, DESIGN.md, B1/B3/B7/B8, OpenAPI types + drift check, fixture script, `<Fact>` + T1/T2, new two-theme tokens (stage always dark) + AA tests, self-hosted fonts + licence, Radix primitives | no screens; all contract tests green |
| U1 | Shell + **On Air** stage (score bug, lower third, seal, SYNTHETIC mark, ball trail, transport, timeline, dwell) + B2 | flows with real data; screenshot review |
| U2 | **Proof**: moment rail, Receipt, metric glossary | T1–T2 pass on real cards; unmatched claim count reported |
| U3 | Trace tape, Rejected takes, Red pen, Method (fixtures first, then agent/eval data) | numbers from JSON |
| U4 | Fan/Analyst, favourite team, player focus | deterministic filters; honest empty states |
| U5 | `/overlay`, capture mode + tour, safe-area guides, a11y / colour-blindness review, mobile, polish | B2–B8 checked; Lighthouse; screenshots |

Cut order inside the UI: tour → player focus → ball trail animation → mobile polish. Never cut: On Air
stage, Receipt, T1–T9 tests, Method.

## 12. Decisions (2026-10-14)
1. Concept approved (On Air / Proof, Flip, Red pen, Rejected takes).
2. Dark + light theme; the program stage is dark in both; both themes AA-tested.
3. Radix UI: yes. Self-hosted fonts: yes. Licences checked in U0.
4. UI before the agent work.
5. Overlay route and tour/capture mode are in scope (U5).
6. Player focus shows an unnarrated, clearly labelled event log.
