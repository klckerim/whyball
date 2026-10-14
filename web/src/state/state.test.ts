import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { matchFixtures } from "../test/fixtures";
import { clockReducer, SPEEDS, wallSeconds } from "./clock";
import { dwellMs, dwellReducer, EMPTY_DWELL, MIN_DWELL_MS, READING_CPS } from "./dwell";
import { arrivals, BALL, ballAt, eventAt, momentsUntil, positioned, stepMoment, trail } from "./match";
import { type Card, initialPlayback, playbackReducer, TICK_MS, usePlayback } from "./playback";

const match = matchFixtures.find((m) => m.summary.id === "red_card_swing_seed42")!;
const { events, moments, detail } = match;
const points = positioned(events);
const cards: Card[] = moments.map((m) => ({ id: m.id, t: m.t, text: m.text }));
const duration = detail.duration_t;

describe("clock", () => {
  const s0 = { t: 0, playing: false, speed: 60, duration };

  it("advances by wall time × speed while playing, and stops at the end", () => {
    const s = clockReducer(clockReducer(s0, { type: "play" }), { type: "tick", dtMs: 1000 });
    expect(s.t).toBe(60);
    expect(clockReducer({ ...s0, playing: false }, { type: "tick", dtMs: 1000 }).t).toBe(0);
    const end = clockReducer({ ...s0, t: duration - 1, playing: true }, { type: "tick", dtMs: 1000 });
    expect(end).toMatchObject({ t: duration, playing: false });
  });

  it("seeks within the match and restarts from kickoff at the end", () => {
    expect(clockReducer(s0, { type: "seek", t: -5 }).t).toBe(0);
    expect(clockReducer(s0, { type: "seek", t: duration + 99 }).t).toBe(duration);
    expect(clockReducer({ ...s0, t: duration }, { type: "play" })).toMatchObject({ t: 0, playing: true });
    expect(clockReducer(s0, { type: "toggle" }).playing).toBe(true);
  });

  it("speeds use the replay API unit and state their wall time", () => {
    expect(SPEEDS.map((s) => s.speed)).toEqual([60, 120, 300]);
    expect(wallSeconds(5400, 60)).toBe(90);
  });
});

describe("match selectors", () => {
  it("eventAt is the event in effect, with its own score", () => {
    const goal = detail.timeline.find((e) => e.type === "goal")!;
    expect(eventAt(events, goal.t)!.score).toEqual(eventAt(events, goal.t + 1)!.score);
    expect(eventAt(events, goal.t)!.score).toEqual(goal.score);
    expect(eventAt(events, 0)!.type).not.toBe("match_meta");
    expect(eventAt(events, duration)!.type).toBe("full_time");
  });

  it("the ball comes only from positioned events, never from a null", () => {
    expect(points.every((p) => p.x !== null && p.y !== null)).toBe(true);
    expect(ballAt(points, -1, true)).toBeNull();
    expect(ballAt([], 100, true)).toBeNull();
    for (const e of events.filter((e) => e.x === null && e.type !== "match_meta")) {
      const b = ballAt(points, e.t, false)!;
      const src = events.find((x) => x.seq === b.seq)!;
      expect([src.x, src.y]).toEqual([b.x, b.y]); // a card or whistle keeps the last real position
    }
  });

  it("interpolates between close events, holds across a gap or into a kickoff", () => {
    const i = points.findIndex((p, k) => {
      const n = points[k + 1];
      return n && n.t - p.t > 1 && n.t - p.t <= BALL.gapS && n.type !== "kickoff";
    });
    const [p, n] = [points[i]!, points[i + 1]!];
    const mid = (p.t + n.t) / 2;
    expect(ballAt(points, mid, true)).toMatchObject({ x: (p.x + n.x) / 2, y: (p.y + n.y) / 2, seq: p.seq });
    expect(ballAt(points, mid, false)).toMatchObject({ x: p.x, y: p.y });
    const g = points.findIndex((q, k) => points[k + 1] && points[k + 1]!.t - q.t > BALL.gapS);
    const q = points[g]!;
    expect(ballAt(points, q.t + 1, true)).toMatchObject({ x: q.x, y: q.y });
  });

  it("the trail is recent, bounded, oldest first and starts at most at a kickoff", () => {
    for (const t of [600, 1800, 3000, duration]) {
      const tr = trail(points, t);
      expect(tr.length).toBeLessThanOrEqual(BALL.trailMax);
      const ts = tr.map((p) => events.find((e) => e.seq === p.seq)!);
      expect(ts.every((e) => t - e.t <= BALL.trailS)).toBe(true);
      expect(ts.slice(1).every((e) => e.type !== "kickoff")).toBe(true);
      expect(ts.map((e) => e.t)).toEqual([...ts.map((e) => e.t)].sort((a, b) => a - b));
    }
  });

  it("arrivals, moments until t and stepping", () => {
    expect(arrivals(moments, -1, duration).map((m) => m.id)).toEqual(moments.map((m) => m.id));
    const m = moments[2]!;
    expect(arrivals(moments, m.t - 1, m.t)).toContain(m);
    expect(arrivals(moments, m.t, m.t + 1)).not.toContain(m);
    expect(momentsUntil(moments, m.t)).toContain(m);
    expect(stepMoment(moments, 0, m.id, 1)).toBe(moments[3]);
    expect(stepMoment(moments, 0, m.id, -1)).toBe(moments[1]);
    expect(stepMoment(moments, 0, moments[0]!.id, -1)).toBeNull();
    expect(stepMoment(moments, m.t, null, 1)!.t).toBeGreaterThan(m.t);
    expect(stepMoment(moments, m.t, null, -1)!.t).toBeLessThan(m.t);
  });
});

describe("dwell", () => {
  const a = { id: "a", text: "x".repeat(10) };
  const b = { id: "b", text: "y".repeat(300) };

  it("lasts max(4 s, reading time)", () => {
    expect(dwellMs(a.text)).toBe(MIN_DWELL_MS);
    expect(dwellMs(b.text)).toBe(Math.round((300 / READING_CPS) * 1000));
  });

  it("queues FIFO and moves on after the dwell", () => {
    let s = dwellReducer(EMPTY_DWELL, { type: "arrive", cards: [a, b] });
    expect(s.current!.id).toBe("a");
    expect(s.queue.map((c) => c.id)).toEqual(["b"]);
    s = dwellReducer(s, { type: "tick", dtMs: MIN_DWELL_MS - 1 });
    expect(s.current!.id).toBe("a");
    s = dwellReducer(s, { type: "tick", dtMs: 1 });
    expect(s.current!.id).toBe("b");
    s = dwellReducer(s, { type: "tick", dtMs: dwellMs(b.text) });
    expect(s).toEqual(EMPTY_DWELL);
  });

  it("clear empties it; show replaces at once", () => {
    const s = dwellReducer(EMPTY_DWELL, { type: "arrive", cards: [a, b] });
    expect(dwellReducer(s, { type: "clear" })).toEqual(EMPTY_DWELL);
    expect(dwellReducer(s, { type: "show", card: b })).toEqual({ current: { id: "b", remainingMs: dwellMs(b.text) }, queue: [] });
  });
});

describe("playback", () => {
  const reduce = playbackReducer(cards);
  const first = cards[0]!;

  it("cards arrive as the clock passes them; seek clears; showMoment jumps", () => {
    let s = initialPlayback(duration, 60, first.t - 1, null, cards);
    expect(s.dwell.current).toBeNull();
    s = reduce(s, { type: "play" });
    s = reduce(s, { type: "tick", dtMs: 100 }); // 6 match seconds: passes the first card
    expect(s.dwell.current!.id).toBe(first.id);
    s = reduce(s, { type: "seek", t: 0 });
    expect(s.dwell).toEqual(EMPTY_DWELL);
    s = reduce(s, { type: "showMoment", id: cards[3]!.id });
    expect(s.clock.t).toBe(cards[3]!.t);
    expect(s.dwell.current!.id).toBe(cards[3]!.id);
  });

  it("opens on a deep-linked card", () => {
    expect(initialPlayback(duration, 60, 0, cards[4]!.id, cards).dwell.current!.id).toBe(cards[4]!.id);
    expect(initialPlayback(duration, 60, 0, "nope", cards).dwell.current).toBeNull();
  });

  describe("timer", () => {
    beforeEach(() => vi.useFakeTimers());
    afterEach(() => vi.useRealTimers());

    it("counts wall time only while playing", () => {
      const { result } = renderHook(() => usePlayback(cards, () => initialPlayback(duration, 60, 0, first.id, cards)));
      const remaining = () => result.current[0].dwell.current?.remainingMs;
      const start = remaining()!;
      act(() => vi.advanceTimersByTime(2000)); // paused: nothing moves
      expect(remaining()).toBe(start);
      expect(result.current[0].clock.t).toBe(first.t);
      act(() => result.current[1]({ type: "play" }));
      act(() => vi.advanceTimersByTime(10 * TICK_MS));
      expect(result.current[0].clock.t).toBeCloseTo(first.t + 60, 5);
      expect(remaining()).toBe(start - 10 * TICK_MS);
      act(() => result.current[1]({ type: "pause" }));
      const paused = result.current[0].clock.t;
      act(() => vi.advanceTimersByTime(5000));
      expect(result.current[0].clock.t).toBe(paused);
    });
  });
});
