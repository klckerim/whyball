// Test-only access to web/test-fixtures/ (built by `python -m app.api.fixtures` from the real API over
// the publication store). Never import this from app code: fixtures stay out of the bundle (UI_SPEC T7).
import type { MatchDetail, MatchSummary, Metrics, Moment, Series, TimelineEvent } from "../api/types";

const raw = import.meta.glob<string>("../../test-fixtures/*.json", { query: "?raw", import: "default", eager: true });

/** File name → exact file text. */
export const fixtureFiles: Record<string, string> = Object.fromEntries(
  Object.entries(raw).map(([path, text]) => [path.slice(path.lastIndexOf("/") + 1), text]),
);

export interface Manifest {
  generator: string;
  sources: Record<string, string>;
  files: Record<string, string>;
}

export interface MatchFixture {
  summary: MatchSummary;
  detail: MatchDetail;
  moments: Moment[];
  events: TimelineEvent[];
  series: Series; // pressure_balance, step 60
}

export const manifest: Manifest = JSON.parse(fixtureFiles["manifest.json"]!);
export const metricsFixture: Metrics = JSON.parse(fixtureFiles["metrics.json"]!);
export const matchFixtures: MatchFixture[] = Object.entries(fixtureFiles)
  .filter(([name]) => name !== "manifest.json" && name !== "metrics.json")
  .map(([, text]) => JSON.parse(text));
