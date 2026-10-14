// Lower-third dwell (UI_SPEC B6, docs/DESIGN.md D16): a card stays on screen for
// max(MIN_DWELL_MS, reading time), counted in wall-clock time while playing; later cards wait in a FIFO.

export const MIN_DWELL_MS = 4000; // UI_SPEC B6
/** Reading speed for the dwell, characters per second. A design parameter, not a standard. */
export const READING_CPS = 15;

export function dwellMs(text: string): number {
  return Math.max(MIN_DWELL_MS, Math.round((text.length / READING_CPS) * 1000));
}

export interface Shown {
  id: string;
  remainingMs: number;
}

export interface DwellState {
  current: Shown | null;
  queue: Shown[];
}

export type DwellAction =
  | { type: "arrive"; cards: { id: string; text: string }[] }
  | { type: "tick"; dtMs: number } // only while playing
  | { type: "clear" } // seek
  | { type: "show"; card: { id: string; text: string } }; // previous/next: at once

export const EMPTY_DWELL: DwellState = { current: null, queue: [] };

const shown = (c: { id: string; text: string }): Shown => ({ id: c.id, remainingMs: dwellMs(c.text) });

export function dwellReducer(s: DwellState, a: DwellAction): DwellState {
  switch (a.type) {
    case "arrive": {
      if (a.cards.length === 0) return s;
      const queue = [...s.queue, ...a.cards.map(shown)];
      return s.current ? { current: s.current, queue } : { current: queue[0]!, queue: queue.slice(1) };
    }
    case "tick": {
      if (!s.current || a.dtMs <= 0) return s;
      const remainingMs = s.current.remainingMs - a.dtMs;
      if (remainingMs > 0) return { ...s, current: { ...s.current, remainingMs } };
      return { current: s.queue[0] ?? null, queue: s.queue.slice(1) };
    }
    case "clear":
      return EMPTY_DWELL;
    case "show":
      return { current: shown(a.card), queue: [] };
  }
}
