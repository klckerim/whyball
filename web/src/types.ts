// Mirrors the API models (app/api/main.py, app/publish/schema.py).

export type Side = "home" | "away";
export type Source = "llm" | "template" | "template_fallback";

export interface Teams {
  home: string;
  away: string;
}

export interface Score {
  home: number;
  away: number;
}

export interface MatchSummary {
  id: string;
  teams: Teams;
  final_score: Score;
  moments: number;
  sources: Record<Source, number>;
}

/** One match event; `t` is seconds since kickoff, continuous across half time. */
export interface MatchEvent {
  seq: number;
  t: number;
  period: number;
  minute: number;
  second: number;
  minute_label: string;
  type: string;
  team: Side | null;
  player: string | null;
  outcome: string | null;
  score: Score;
}

export interface Period {
  period: number;
  start_t: number;
  end_t: number;
}

export interface MatchDetail {
  id: string;
  event_match_id: string;
  teams: Teams;
  final_score: Score;
  duration_t: number;
  periods: Period[];
  timeline: MatchEvent[];
  run_id: string;
  prompt_version: string;
}

export interface EvidenceEvent {
  id: string;
  seq: number;
  type: string;
  team: Side | null;
  player: string | null;
  period: number;
  minute: number;
  second: number;
  minute_label: string;
  /** Pitch position from the event stream (0..105, 0..68); null for cards and substitutions. */
  x?: number | null;
  y?: number | null;
}

export interface Claim {
  id: string;
  kind: string;
  metric: string;
  label: string;
  team: Side | null;
  player: string | null;
  comparison: string;
  value: number;
  display: string;
  start: string;
  end: string;
  evidence: EvidenceEvent[];
}

/** One step of the narration pipeline trace (app/explain/pipeline.py `run_moment`). */
export interface TraceStep {
  attempt: number;
  step: "cache" | "narrate" | "lint" | "verify" | "feedback" | "accept" | "cache_store" | "fallback";
  ok: boolean;
  narrator?: string;
  source?: string;
  reason?: string;
  codes?: string[];
  issues?: { code: string; fragment: string }[];
  results?: { claim_index: number; ok: boolean; reason: string }[];
  [key: string]: unknown;
}

export interface Moment {
  id: string;
  t: number;
  period: number;
  minute: number;
  second: number;
  minute_label: string;
  at_seq: number;
  type: string;
  team: Side | null;
  importance: number;
  text: string;
  source: Source;
  prompt_version: string;
  run_id: string | null;
  claims: Claim[];
  trace: TraceStep[];
}
