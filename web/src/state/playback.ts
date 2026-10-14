// Clock + dwell in one reducer: a tick moves the clock, cards whose time it passed arrive in the dwell
// queue, and the card on screen counts down its wall-clock dwell. One timer drives both.
import { useEffect, useReducer } from "react";

import { type ClockState, clockReducer } from "./clock";
import { type DwellState, dwellReducer, EMPTY_DWELL } from "./dwell";
import { arrivals } from "./match";

export const TICK_MS = 100;

export interface Card {
  id: string;
  t: number;
  text: string;
}

export interface Playback {
  clock: ClockState;
  dwell: DwellState;
}

export type PlaybackAction =
  | { type: "play" }
  | { type: "pause" }
  | { type: "toggle" }
  | { type: "seek"; t: number }
  | { type: "setSpeed"; speed: number }
  | { type: "tick"; dtMs: number }
  | { type: "showMoment"; id: string };

export function playbackReducer(cards: readonly Card[]) {
  return (s: Playback, a: PlaybackAction): Playback => {
    switch (a.type) {
      case "tick": {
        if (!s.clock.playing) return s;
        const clock = clockReducer(s.clock, a);
        const dwell = dwellReducer(dwellReducer(s.dwell, a), {
          type: "arrive",
          cards: arrivals(cards, s.clock.t, clock.t),
        });
        return { clock, dwell };
      }
      case "seek":
        return { clock: clockReducer(s.clock, a), dwell: dwellReducer(s.dwell, { type: "clear" }) };
      case "showMoment": {
        const card = cards.find((c) => c.id === a.id);
        if (!card) return s;
        return {
          clock: clockReducer(s.clock, { type: "seek", t: card.t }),
          dwell: dwellReducer(s.dwell, { type: "show", card }),
        };
      }
      default:
        return { ...s, clock: clockReducer(s.clock, a) };
    }
  };
}

export function initialPlayback(duration: number, speed: number, t: number, showId: string | null, cards: readonly Card[]): Playback {
  const base: Playback = { clock: { t: 0, playing: false, speed, duration }, dwell: EMPTY_DWELL };
  const reduce = playbackReducer(cards);
  return showId && cards.some((c) => c.id === showId)
    ? reduce(base, { type: "showMoment", id: showId })
    : reduce(base, { type: "seek", t });
}

/** The reducer plus the timer that ticks it while playing (wall-clock dt from Date.now). */
export function usePlayback(cards: readonly Card[], init: () => Playback) {
  const [state, dispatch] = useReducer(playbackReducer(cards), undefined, init);
  const playing = state.clock.playing;
  useEffect(() => {
    if (!playing) return;
    let last = Date.now();
    const id = setInterval(() => {
      const now = Date.now();
      dispatch({ type: "tick", dtMs: now - last });
      last = now;
    }, TICK_MS);
    return () => clearInterval(id);
  }, [playing]);
  return [state, dispatch] as const;
}
