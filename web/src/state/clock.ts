// Replay clock (docs/DESIGN.md D14): the stage plays the fetched events with a client clock, so seeking
// is exact and tests are deterministic. `t` is seconds since kickoff on the API's continuous axis.

/** Speeds in match seconds per wall-clock second: the same unit as the replay API `speed` (D15).
 * Normal plays a 90-minute match in about 60 minutes, slow enough for a card's reading dwell (D16) to fit
 * between moments; Fast is about 15 minutes, Faster about 3. */
export const SPEEDS = [
  { id: "normal", label: "1×", speed: 1.5 },
  { id: "fast", label: "Fast", speed: 6 },
  { id: "faster", label: "Faster", speed: 30 },
] as const;

export type SpeedId = (typeof SPEEDS)[number]["id"];

/** Wall-clock seconds the whole match takes at `speed` (shown next to the speed choice). */
export function wallSeconds(duration: number, speed: number): number {
  return Math.round(duration / speed);
}

/** The wall time as words: seconds under two minutes, else whole minutes. */
export function wallLabel(duration: number, speed: number): string {
  const s = wallSeconds(duration, speed);
  return s < 120 ? `${s} s` : `${Math.round(s / 60)} min`;
}

export interface ClockState {
  t: number;
  playing: boolean;
  speed: number;
  duration: number;
}

export type ClockAction =
  | { type: "play" }
  | { type: "pause" }
  | { type: "toggle" }
  | { type: "seek"; t: number }
  | { type: "setSpeed"; speed: number }
  | { type: "tick"; dtMs: number };

const clamp = (t: number, duration: number) => Math.min(duration, Math.max(0, t));

export function clockReducer(s: ClockState, a: ClockAction): ClockState {
  switch (a.type) {
    case "play":
      // at the final whistle, play starts again from kickoff
      return { ...s, playing: s.duration > 0, t: s.t >= s.duration ? 0 : s.t };
    case "pause":
      return { ...s, playing: false };
    case "toggle":
      return clockReducer(s, { type: s.playing ? "pause" : "play" });
    case "seek":
      return { ...s, t: clamp(a.t, s.duration) };
    case "setSpeed":
      return { ...s, speed: a.speed };
    case "tick": {
      if (!s.playing || a.dtMs <= 0) return s;
      const t = clamp(s.t + (a.dtMs / 1000) * s.speed, s.duration);
      return { ...s, t, playing: t < s.duration };
    }
  }
}
