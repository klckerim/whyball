# WhyBall Demo Dataset — Datasheet

## 1. Purpose and scope

**Fully synthetic** football match event streams, generated to feed WhyBall's analytics, moment detector and narration (explain + verifier) stages.

- Each match is generated deterministically from an integer seed. The same seed and scenario produce a byte-identical file in every environment.
- Team and player names are picked from made-up name pools ([app/generator/names.py](../app/generator/names.py)). No real club, player or match is included.
- There is no personal data.

## 2. Generation method

Source: [app/generator/engine.py](../app/generator/engine.py). No LLM is used for generation.

- **Randomness:** A single `random.Random(seed)` instance. The global `random`, the clock, `uuid` and hash/set order are never used.
- **Model:** A possession state machine. The clock advances 2–20 s per step. A weighted action is picked for the side in possession: pass, dribble, shot, foul, offside. How close the ball is to the opponent's goal (`progress`) sets the shot and offside probabilities.
  - **Shot** → goal / save / block / off target. Blocks and saves can turn into corners.
  - **Foul** → a card may follow. Some fouls in the penalty area lead to a penalty.
  - **Other:** 1–3 substitutions in the second half. Each missing player on the pitch raises the turnover probability.
- **Calibration:** In mode without a scenario, per-match averages over 3000 seeds:

  | Goals | Shots | Corners | Yellow | Red | Penalties |
  |---|---|---|---|---|---|
  | 2.8 | 20.2 | 5.3 | 3.9 | 0.10 | 0.25 |

  These averages are tested within wide ranges (`test_averages_over_200_seeds_are_realistic`).
- **Determinism guarantee:** `tests/test_generator.py` checks that a seed gives the same output in the same process and in separate processes started with different `PYTHONHASHSEED` values. `tests/test_demo_fixtures.py` checks that the demo files in the repo are identical to the generator output at the SHA-256 level.

## 3. Schema (version 1)

Format: JSONL. Each line is one event. Keys are sorted alphabetically, separators have no spaces, line ending `\n`, encoding UTF-8.

### Event fields

| Field | Type | Nullable | Meaning |
|---|---|---|---|
| `match_id` | string | no | `m-{seed}` or `m-{seed}-{scenario}` |
| `seq` | int | no | Gapless sequence number starting at 0 |
| `period` | int | no | 1 or 2 |
| `minute`, `second` | int | no | Match clock. The second half starts at 45:00; stoppage time continues as 45+ / 90+ minutes. Sort by `(period, minute, second)`. |
| `type` | string | no | Event type, see the table below |
| `team` | string | yes | `home` / `away`. The team making the event (for fouls and cards, the team penalized) |
| `player` | string | yes | The player making the event |
| `x`, `y` | float | yes | Ball position on a 105×68 pitch, 1 decimal. `home` attacks towards x=105 in both halves. Null for card, substitution and period events. |
| `outcome` | string | yes | Pass/dribble: `success`/`fail`. Shot: `goal`/`saved`/`blocked`/`off_target`. Penalty: `scored`/`saved`/`missed`. |
| `score` | object | no | Score **after** the event: `{"away": int, "home": int}` |
| `data` | object | yes | Type-specific extra info |

### Event types

| Type | `team` / `player` | `data` |
|---|---|---|
| `match_meta` | null | `schema`, `seed`, `scenario`, `teams.{home,away}.{name, lineup[11], bench[5]}` (lineup[0] is the goalkeeper) |
| `kickoff` | the side kicking off | — |
| `pass`, `dribble` | the side in possession | — |
| `shot` | the shooter | — |
| `goal` | the scorer; always follows a `shot(goal)` or `penalty(scored)` event | — |
| `save` | the goalkeeper making the save | — |
| `foul` | the player committing the foul | — |
| `yellow_card` | the booked player | — |
| `red_card` | the player sent off | `reason`: `straight_red` / `second_yellow` |
| `penalty` | the penalty taker; always follows a `foul` event (that foul's card may come in between) | — |
| `corner` | the side taking the corner | — |
| `offside` | the player caught offside | — |
| `substitution` | the player **coming off** | `player_in`: the player coming on |
| `half_time`, `full_time` | null | — |

### Invariants (guaranteed by tests)

- `seq` increases without gaps. Time never decreases in `(period, minute, second)` order.
- The stream starts with `match_meta` → `kickoff` and ends with `full_time`. There is exactly one `half_time`.
- The `score` of each event equals the number of `goal` events so far.
- There are never more than 11 players on the pitch. A player involved in an event is on the pitch at that moment.
- A player sent off or substituted never appears again. A player coming on comes from the bench.

## 4. Scenario mode

Source: [app/generator/scenarios.py](../app/generator/scenarios.py). A scenario is a list of forced events at given minutes: goal, red card, penalty (with its outcome).

> **In scenario mode, goals and penalties are scripted; no goal happens on its own.**
> The score comes only from the scenario's forced events. Shots that would be goals in the natural flow are turned into saves, and natural penalties get the `saved` outcome. So the final score is the scenario's score for every seed.
> Everything else (passes, shots, corners, fouls, cards, substitutions) is generated naturally from the seed. Unscripted red cards can also appear in scenario matches.

| Scenario | Forced events | Result | Extra setting |
|---|---|---|---|
| `late_comeback` | away goals 18', 52' · home goal 74' · home penalty (goal) 83' · home goal 89' | 3-2 | — |
| `red_card_swing` | home goal 22' · home red 38' · away goals 61', 84' | 1-2 | — |
| `dominant_loss` | away goal 57' · home penalty (saved) 70' | 0-1 | `turnover_factor` home 0.45 / away 1.25 · `tempo` home 0.5 |

- `turnover_factor`: turnover probability multiplier for passes and dribbles. 1.0 is normal; below 1 means a side that keeps the ball better.
- `tempo`: progression multiplier for passes and dribbles. Below 1 represents patient build-up.
- **Timing:** A forced event happens exactly at the given minute (`mm:00`). If a goal celebration happened right before, it can shift by at most 1 minute.

## 5. Demo matches

Location: `data/demo/`. These files are frozen; if the generator changes, `tests/test_demo_fixtures.py` fails.

| File | Scenario | Seed | Teams (home – away) | Score | Events | SHA-256 (first 12) |
|---|---|---|---|---|---|---|
| `red_card_swing_seed42.jsonl` | red_card_swing | 42 | Brannoch FC – Morvane Athletic | 1-2 | 541 | `f3cd306f1213` |
| `dominant_loss_seed7.jsonl` | dominant_loss | 7 | Vellorin FC – Tessdal Athletic | 0-1 | 573 | `523edd6027a9` |
| `natural_seed100.jsonl` | — | 100 | Tessdal Wanderers – Isteven United | 2-1 | 568 | `8ee57c212c35` |

**red_card_swing, seed 42:** Brannoch go ahead at 22' and are reduced to 10 men by a straight red at 38'. Morvane turn the match around with goals at 61' and 84'. Shots: home 5, away 15.

**dominant_loss, seed 7:** Vellorin dominate the ball. Pass and dribble share 58%, shots 28 to 1, corners 7 to 0. Tessdal score with their only shot at 57'. The goalkeeper saves Vellorin's penalty at 70'.

**natural (no scenario), seed 100:** Isteven are reduced to 10 men by a straight red at 14'. Tessdal go ahead at 29', Isteven equalize at 51', and Tessdal score the winner at 90:13. Shots: home 19, away 4.

## 6. Known limitations

- Free kicks, throw-ins and goal kicks are not separate events. After a foul the ball stays with the fouled side.
- The sides do not switch ends at half time (`home` always attacks towards x=105).
- In a single match the possession share moves by about ±0.04 depending on the seed. The `dominant_loss` dominance is clear on average (61%) but can drop to 50% in a single match.
- Scenario events happen exactly at the start of a minute (`mm:00`), while natural events are spread across seconds. This makes scripted events distinguishable; evaluations need to keep it in mind.
- In `dominant_loss` the weaker side has very few shots (about 3 on average, 1 for seed 7).
- Calibration covers only per-match totals. Per-player distributions (who shoots, etc.) are uniformly random; there is no position model.

## 7. Regenerating

If the generator was changed **on purpose**:

```
.venv/bin/python -m app.generator.freeze
```

The command rewrites the three files and prints the rows of the table in section 5. Then:
1. Update the table and the match stories in section 5.
2. Run `.venv/bin/pytest -q`.

To generate a single match:

```
.venv/bin/python -m app.generator --seed 42 [--scenario late_comeback|red_card_swing|dominant_loss] [--out match.jsonl]
```
