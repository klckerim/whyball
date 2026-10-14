// Pure selectors over the fetched match data at clock time `t` (no UI). Values come from the events'
// own fields; nothing is computed that the stream does not hold, except the visual ball interpolation.
import type { TimelineEvent } from "../api/types";

/** Ball and trail parameters (docs/DESIGN.md D17; design parameters, not a standard). */
export const BALL = {
  /** Two positioned events further apart than this (match seconds) are not joined: the ball holds. */
  gapS: 8,
  /** Trail: positioned events of the last `trailS` match seconds, at most `trailMax` points. */
  trailS: 12,
  trailMax: 6,
} as const;

export interface BallPoint {
  x: number;
  y: number;
  seq: number; // the positioned event the point comes from (the last one at or before t)
}

interface Timed {
  t: number;
}

/** Index of the last item with item.t <= t (items sorted by t), or -1. */
function lastAtOrBefore<T extends Timed>(items: readonly T[], t: number): number {
  let lo = 0;
  let hi = items.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (items[mid]!.t <= t) {
      found = mid;
      lo = mid + 1;
    } else hi = mid - 1;
  }
  return found;
}

/** The match event in effect at `t` (its own score and minute label); match_meta is not a match event. */
export function eventAt(events: readonly TimelineEvent[], t: number): TimelineEvent | null {
  const played = events.filter((e) => e.type !== "match_meta");
  const i = lastAtOrBefore(played, t);
  return i < 0 ? null : played[i]!;
}

type Positioned = TimelineEvent & { x: number; y: number };

export function positioned(events: readonly TimelineEvent[]): Positioned[] {
  return events.filter((e): e is Positioned => e.x !== null && e.y !== null);
}

/** Ball position at `t`; null before the first positioned event ("no location", never 0,0).
 * With `interpolate`, a straight line to the next positioned event unless the gap is over `gapS` or the
 * next event is a kickoff (a restart is a jump, not a pass). Interpolation is visual only. */
export function ballAt(points: readonly Positioned[], t: number, interpolate: boolean): BallPoint | null {
  const i = lastAtOrBefore(points, t);
  if (i < 0) return null;
  const p = points[i]!;
  const n = points[i + 1];
  if (!interpolate || !n || n.t - p.t > BALL.gapS || n.type === "kickoff" || n.t === p.t) {
    return { x: p.x, y: p.y, seq: p.seq };
  }
  const f = (t - p.t) / (n.t - p.t);
  return { x: p.x + (n.x - p.x) * f, y: p.y + (n.y - p.y) * f, seq: p.seq };
}

/** Recent positioned events, oldest first, cut at a gap over `gapS` and at the last kickoff. */
export function trail(points: readonly Positioned[], t: number): BallPoint[] {
  const out: BallPoint[] = [];
  for (let i = lastAtOrBefore(points, t); i >= 0 && out.length < BALL.trailMax; i--) {
    const p = points[i]!;
    if (t - p.t > BALL.trailS) break;
    const newer = points[i + 1];
    if (out.length > 0 && newer && newer.t - p.t > BALL.gapS) break;
    out.unshift({ x: p.x, y: p.y, seq: p.seq });
    if (p.type === "kickoff") break;
  }
  return out;
}

/** Moments whose time falls in (t0, t1], in order. */
export function arrivals<T extends Timed>(moments: readonly T[], t0: number, t1: number): T[] {
  return moments.filter((m) => m.t > t0 && m.t <= t1);
}

export function momentsUntil<T extends Timed>(moments: readonly T[], t: number): T[] {
  return moments.filter((m) => m.t <= t);
}

/** The moment before/after the one shown (by order), or before/after `t` when none is shown. */
export function stepMoment<T extends Timed & { id: string }>(
  moments: readonly T[],
  t: number,
  currentId: string | null,
  dir: -1 | 1,
): T | null {
  const i = currentId ? moments.findIndex((m) => m.id === currentId) : -1;
  if (i >= 0) return moments[i + dir] ?? null;
  if (dir === 1) return moments.find((m) => m.t > t) ?? null;
  return [...moments].reverse().find((m) => m.t < t) ?? null;
}
