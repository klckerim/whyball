import { describe, expect, it } from "vitest";

import {
  assignLanes,
  clockLabel,
  fraction,
  isFeatured,
  minuteLabel,
  runMeta,
  scoreAt,
  scoreboardClock,
  SPEED_OPTIONS,
  teamInitials,
  visibleMoments,
} from "./timeline";
import type { MatchEvent, Moment, Period } from "./types";

// red_card_swing_seed42: first half ends at 47:35 (t=2855), second half restarts at 45:00.
const periods: Period[] = [
  { period: 1, start_t: 0, end_t: 2855 },
  { period: 2, start_t: 2855, end_t: 5729 },
];

const goal = (t: number, home: number, away: number) => ({ t, type: "goal", score: { home, away } }) as MatchEvent;

describe("clock", () => {
  it("formats stoppage time like the narration", () => {
    expect(minuteLabel(1, 22)).toBe("22'");
    expect(minuteLabel(1, 47)).toBe("45+3'");
    expect(minuteLabel(2, 92)).toBe("90+3'");
  });

  it("maps t onto the match clock across half time", () => {
    expect(clockLabel(0, periods)).toBe("0'");
    expect(clockLabel(1320, periods)).toBe("22'");
    expect(clockLabel(2855, periods)).toBe("45+3'");
    expect(clockLabel(2856, periods)).toBe("45'");
    expect(clockLabel(3815, periods)).toBe("61'");
    expect(clockLabel(5729, periods)).toBe("90+3'");
  });
});

describe("scoreAt", () => {
  const timeline = [goal(1320, 1, 0), goal(3815, 1, 1), goal(5195, 1, 2)];
  it("is the score after every event up to t", () => {
    expect(scoreAt(0, timeline)).toEqual({ home: 0, away: 0 });
    expect(scoreAt(1319, timeline)).toEqual({ home: 0, away: 0 });
    expect(scoreAt(1320, timeline)).toEqual({ home: 1, away: 0 });
    expect(scoreAt(5729, timeline)).toEqual({ home: 1, away: 2 });
  });
});

describe("visibleMoments", () => {
  const moments = [{ id: "a", t: 10 }, { id: "b", t: 20 }, { id: "c", t: 30 }] as Moment[];
  it("reveals cards up to t, newest first", () => {
    expect(visibleMoments(moments, 5)).toEqual([]);
    expect(visibleMoments(moments, 20).map((m) => m.id)).toEqual(["b", "a"]);
  });
});

it("clamps the timeline fraction", () => {
  expect(fraction(50, 100)).toBe(0.5);
  expect(fraction(150, 100)).toBe(1);
  expect(fraction(5, 0)).toBe(0);
});

describe("ui helpers", () => {
  it("features model and fallback cards, not plain templates", () => {
    expect(isFeatured({ source: "llm" })).toBe(true);
    expect(isFeatured({ source: "template_fallback" })).toBe(true);
    expect(isFeatured({ source: "template" })).toBe(false);
  });

  it("shows FT at the final whistle", () => {
    expect(scoreboardClock(5729, 5729, periods)).toBe("FT");
    expect(scoreboardClock(1320, 5729, periods)).toBe("22'");
  });

  it("names the existing replay speeds", () => {
    expect(SPEED_OPTIONS.map((s) => [s.value, s.label])).toEqual([[30, "Slow"], [60, "1×"], [120, "Fast"], [300, "Faster"]]);
  });

  it("stacks markers that are too close to each other", () => {
    const lanes = assignLanes(
      [{ id: "a", f: 0.5 }, { id: "b", f: 0.51 }, { id: "c", f: 0.515 }, { id: "d", f: 0.6 }, { id: "e", f: 0.1 }],
      0.02,
    );
    expect(Object.fromEntries(lanes)).toEqual({ e: 0, a: 0, b: 1, c: 2, d: 0 });
  });

  it("derives crest initials without club suffixes", () => {
    expect(teamInitials("Brannoch FC")).toBe("B");
    expect(teamInitials("Morvane Athletic")).toBe("M");
    expect(teamInitials("Port Selvan City")).toBe("PS");
    expect(teamInitials("FC")).toBe("F");
  });

  it("shortens the model and run line", () => {
    expect(runMeta("foundry-v5.2:gpt-5-mini", "foundry-v5.2:gpt-5-mini@2026-10-13T15:02:48+00:00").short).toBe("gpt-5-mini · run 2026-10-13");
    expect(runMeta("template-v1", null)).toEqual({ short: "template-v1", full: "Prompt template-v1" });
  });
});
