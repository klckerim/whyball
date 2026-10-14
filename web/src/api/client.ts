// Typed fetches for the new UI (types generated from OpenAPI). A 404 is its own error so a screen can
// say "not found" instead of "something failed".
import type { MatchDetail, MatchSummary, Metrics, Moment, Series, TimelineEvent } from "./types";

export class NotFoundError extends Error {}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (res.status === 404) throw new NotFoundError(path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

const m = (id: string) => `/api/matches/${encodeURIComponent(id)}`;

export const api = {
  matches: () => get<MatchSummary[]>("/api/matches"),
  detail: (id: string) => get<MatchDetail>(m(id)),
  moments: (id: string) => get<Moment[]>(`${m(id)}/moments`),
  events: (id: string) => get<TimelineEvent[]>(`${m(id)}/events`),
  series: (id: string, metric: string, step: number) =>
    get<Series>(`${m(id)}/series?${new URLSearchParams({ metric, step: String(step) })}`),
  metrics: () => get<Metrics>("/api/metrics"),
};
