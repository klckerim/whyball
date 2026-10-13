import { describe, expect, it } from "vitest";

import { defaultClaim, markClaims } from "./claimText";
import type { Claim, Moment } from "./types";

// Texts and claims from data/demo_narration/red_card_swing_seed42.json.
const claim = (id: string, metric: string, display: string, start: string, end: string, over: Partial<Claim> = {}): Claim => ({
  id, metric, display, start, end, kind: "count", label: metric, team: null, player: null, comparison: "eq", value: 0, evidence: [], ...over,
});

const marked = (text: string, claims: Claim[]) =>
  markClaims(text, claims).filter((s) => s.claimId).map((s) => [s.text, s.claimId]);

describe("markClaims", () => {
  it("marks player, minute, percentage and the score pair of a goal card", () => {
    const text = "Murek Brestani scored at 22', and Brannoch FC have had 55% of the ball since kickoff. The score is Brannoch FC 1–0 Morvane Athletic.";
    const claims = [
      claim("goal", "goals", "1", "22'", "22'", { player: "Murek Brestani", team: "home" }),
      claim("possession", "possession", "55%", "0'", "22'", { team: "home" }),
      claim("score_home", "score", "1", "0'", "22'", { team: "home" }),
      claim("score_away", "score", "0", "0'", "22'", { team: "away" }),
    ];
    expect(marked(text, claims)).toEqual([
      ["Murek Brestani", "goal"],
      ["22'", "goal"],
      ["55%", "possession"],
      ["1", "score_home"],
      ["0", "score_away"],
    ]);
    expect(markClaims(text, claims).map((s) => s.text).join("")).toBe(text);
  });

  it("keeps counts in claim order and skips digits inside minutes and other numbers", () => {
    const text = "13' — Brannoch FC take control: pressure balance over the last 10 minutes of play is +0.75 in their favour. Shots since 3': Brannoch FC 1, Morvane Athletic 0.";
    const claims = [
      claim("pressure_balance_home", "pressure_balance", "+0.75", "0'", "13'"),
      claim("shots_home", "shots", "1", "3'", "13'"),
      claim("shots_away", "shots", "0", "3'", "13'"),
    ];
    expect(marked(text, claims)).toEqual([
      ["13'", "pressure_balance_home"],
      ["+0.75", "pressure_balance_home"],
      ["3'", "shots_home"],
      ["1", "shots_home"],
      ["0", "shots_away"],
    ]);
  });

  it("does not give a worded metric (margin, goals) a bare number", () => {
    const text = "Murek Ymberto scored at 84', and Morvane Athletic came from behind to take the lead, having trailed by 1 goal earlier in the match. The score is Brannoch FC 1–2 Morvane Athletic and Morvane Athletic have had 50% of the ball since kickoff.";
    const claims = [
      claim("goal", "goals", "1", "84'", "84'", { player: "Murek Ymberto" }),
      claim("margin", "score_margin", "1", "0'", "84'"),
      claim("deficit", "min_score_margin", "1", "0'", "84'"),
      claim("score_home", "score", "1", "0'", "84'", { team: "home" }),
      claim("score_away", "score", "2", "0'", "84'", { team: "away" }),
      claim("possession", "possession", "50%", "0'", "84'"),
    ];
    expect(marked(text, claims)).toEqual([
      ["Murek Ymberto", "goal"],
      ["84'", "goal"],
      ["1", "deficit"],
      ["1", "score_home"],
      ["2", "score_away"],
      ["50%", "possession"],
    ]);
  });
});

it("picks the first claim backed by events", () => {
  const ev = { id: "e", seq: 1, type: "shot", team: null, player: null, period: 1, minute: 1, second: 0, minute_label: "1'" };
  const m = { claims: [claim("a", "shots", "0", "0'", "1'"), claim("b", "shots", "1", "0'", "1'", { evidence: [ev] })] } as Moment;
  expect(defaultClaim(m)?.id).toBe("b");
  expect(defaultClaim({ claims: [] as Claim[] } as Moment)).toBeNull();
});
