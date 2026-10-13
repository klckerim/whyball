import type { MatchDetail, MatchSummary, Moment } from "./types";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${path}: ${res.status} ${res.statusText}`);
  return (await res.json()) as T;
}

export const fetchMatches = () => get<MatchSummary[]>("/api/matches");
export const fetchMatch = (id: string) => get<MatchDetail>(`/api/matches/${encodeURIComponent(id)}`);
export const fetchMoments = (id: string) => get<Moment[]>(`/api/matches/${encodeURIComponent(id)}/moments`);

export function replayUrl(id: string, speed: number, fromT: number): string {
  const q = new URLSearchParams({ speed: String(speed), from_t: String(Math.max(0, Math.floor(fromT))) });
  return `/api/matches/${encodeURIComponent(id)}/replay?${q}`;
}
