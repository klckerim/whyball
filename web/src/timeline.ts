import type { MatchEvent, Moment, Period, Score, Source } from "./types";

const SECOND_HALF_CLOCK = 45 * 60;

/** Same form as the narration ("45+2'", "90+1'"); app/explain/template_narrator.py fmt_minute. */
export function minuteLabel(period: number, minute: number): string {
  if (period === 1 && minute >= 45) return `45+${minute - 44}'`;
  if (period === 2 && minute >= 90) return `90+${minute - 89}'`;
  return `${minute}'`;
}

/** Match clock at `t` (seconds since kickoff): period and minute. */
export function clockAt(t: number, periods: Period[]): { period: number; minute: number } {
  const second = periods.find((p) => p.period === 2);
  if (!second || t <= second.start_t) return { period: 1, minute: Math.floor(t / 60) };
  return { period: 2, minute: Math.floor((SECOND_HALF_CLOCK + t - second.start_t) / 60) };
}

export function clockLabel(t: number, periods: Period[]): string {
  const { period, minute } = clockAt(t, periods);
  return minuteLabel(period, minute);
}

/** Score after every event up to `t` (the timeline holds every goal). */
export function scoreAt(t: number, timeline: MatchEvent[]): Score {
  let score: Score = { home: 0, away: 0 };
  for (const e of timeline) {
    if (e.t > t) break;
    score = e.score;
  }
  return score;
}

/** Cards revealed by `t`, newest first. */
export function visibleMoments(moments: Moment[], t: number): Moment[] {
  return moments.filter((m) => m.t <= t).reverse();
}

export function fraction(t: number, duration: number): number {
  return duration > 0 ? Math.min(1, Math.max(0, t / duration)) : 0;
}

export const SOURCE_META: Record<Source, { label: string; glyph: string; title: string }> = {
  llm: { label: "LLM · verified", glyph: "◆", title: "Model draft that passed lint and claim verification" },
  template: { label: "Template", glyph: "■", title: "Template narration (moment not selected for the model)" },
  template_fallback: {
    label: "Template fallback",
    glyph: "▲",
    title: "The model draft did not pass verification; the template narration was published instead",
  },
};

const TYPE_LABELS: Record<string, string> = {
  goal: "Goal",
  red_card: "Red card",
  penalty: "Penalty",
  pressure_shift: "Pressure shift",
  dominance_without_reward: "Dominance without reward",
};

export function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type.replace(/_/g, " ");
}

export function eventLabel(type: string): string {
  return type.replace(/_/g, " ");
}

/** Shown by default: model narrations and moments selected for the model (published or fallback). */
export function isFeatured(m: Pick<Moment, "source">): boolean {
  return m.source !== "template";
}

/** Clock shown on the scoreboard: "FT" once the replay reaches the final whistle. */
export function scoreboardClock(t: number, duration: number, periods: Period[]): string {
  return duration > 0 && t >= duration ? "FT" : clockLabel(t, periods);
}

/** Replay speeds in match seconds per second (the API `speed`), with plain names. */
export const SPEED_OPTIONS: { value: number; label: string; title: string }[] = [
  { value: 30, label: "Slow", title: "Half a match minute per second" },
  { value: 60, label: "1×", title: "One match minute per second" },
  { value: 120, label: "Fast", title: "Two match minutes per second" },
  { value: 300, label: "Faster", title: "Five match minutes per second" },
];

/** Vertical lane per timeline marker so markers closer than `minGap` (a fraction of the track)
 * stack instead of covering each other. Input order does not matter; lanes are reused. */
export function assignLanes(items: { id: string; f: number }[], minGap: number): Map<string, number> {
  const lastInLane: number[] = [];
  const lanes = new Map<string, number>();
  for (const it of [...items].sort((a, b) => a.f - b.f)) {
    let lane = lastInLane.findIndex((f) => it.f - f >= minGap);
    if (lane === -1) lane = lastInLane.length;
    lastInLane[lane] = it.f;
    lanes.set(it.id, lane);
  }
  return lanes;
}

const CLUB_WORDS = new Set(["fc", "afc", "cf", "sc", "ac", "athletic", "united", "city", "town", "club"]);

/** One or two letters for the crest: "Brannoch FC" → "B", "Port Selvan City" → "PS". */
export function teamInitials(name: string): string {
  const words = name.split(/\s+/).filter(Boolean);
  const core = words.filter((w) => !CLUB_WORDS.has(w.toLowerCase()));
  const use = core.length ? core : words;
  return use
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("");
}

/** Short model/run line for a card and the full form for its tooltip. */
export function runMeta(promptVersion: string, runId: string | null): { short: string; full: string } {
  const model = promptVersion.includes(":") ? promptVersion.slice(promptVersion.indexOf(":") + 1) : promptVersion;
  const date = runId?.match(/@(\d{4}-\d{2}-\d{2})/)?.[1];
  return {
    short: date ? `${model} · run ${date}` : model,
    full: runId ? `Prompt ${promptVersion}\nRun ${runId}` : `Prompt ${promptVersion}`,
  };
}
