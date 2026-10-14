// Evidence events of a card joined with the event stream (/events) by `seq`: the stream holds the
// outcome, and a position when the evidence record has none. Pure; no UI.
import type { Evidence, TimelineEvent } from "../api/types";

export interface EvidenceRow extends Evidence {
  outcome: string | null;
  /** Ball position at the event, null when the stream has none (cards, substitutions, whistles). */
  at: { x: number; y: number } | null;
}

export function joinEvidence(ev: Evidence, bySeq: ReadonlyMap<number, TimelineEvent>): EvidenceRow {
  const streamed = bySeq.get(ev.seq);
  const x = ev.x ?? streamed?.x ?? null;
  const y = ev.y ?? streamed?.y ?? null;
  return { ...ev, outcome: streamed?.outcome ?? null, at: x !== null && y !== null ? { x, y } : null };
}

export function bySeq(events: readonly TimelineEvent[]): Map<number, TimelineEvent> {
  return new Map(events.map((e) => [e.seq, e]));
}

/** Rows of the evidence, in event order, each event once (several claims can share an event). */
export function rowsOf(evidence: readonly Evidence[], index: ReadonlyMap<number, TimelineEvent>): EvidenceRow[] {
  const unique = [...new Map(evidence.map((e) => [e.id, e])).values()];
  return unique.map((e) => joinEvidence(e, index)).sort((a, b) => a.seq - b.seq);
}
