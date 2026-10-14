// Thin pressure_balance band behind the timeline (B2 series): home above the centre line, away below.
// No values are written; a null point is a gap, never a zero. Name and definition come from the API.
import type { MatchDetail, Series } from "../api/types";
import { Fact } from "../design/Fact";
import styles from "./app.module.css";

const W = 1000; // viewBox units across the match
const MID = 50;
const AMP = 46;

/** Area paths, one per run of non-null points (a gap splits the band). */
export function bandPaths(series: Series, duration: number): string[] {
  const runs: { x: number; y: number }[][] = [];
  let run: { x: number; y: number }[] = [];
  for (const p of series.points) {
    if (p.value === null) {
      if (run.length) runs.push(run);
      run = [];
      continue;
    }
    run.push({ x: duration > 0 ? (p.t / duration) * W : 0, y: MID - p.value * AMP });
  }
  if (run.length) runs.push(run);
  return runs
    .filter((r) => r.length > 1)
    .map((r) => `M${r[0]!.x},${MID} ${r.map((p) => `L${p.x},${p.y}`).join(" ")} L${r[r.length - 1]!.x},${MID} Z`);
}

export function PressureBand({ series, duration }: { series: Series; duration: number }) {
  const paths = bandPaths(series, duration);
  return (
    <svg
      className={styles.band}
      viewBox={`0 0 ${W} ${MID * 2}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`${series.label}, home side above the line and away side below; values not shown. ${series.definition}`}
    >
      <defs>
        <clipPath id="band-home">
          <rect x="0" y="0" width={W} height={MID} />
        </clipPath>
        <clipPath id="band-away">
          <rect x="0" y={MID} width={W} height={MID} />
        </clipPath>
      </defs>
      {paths.map((d) => (
        <g key={d}>
          <path d={d} className={styles.bandHome} clipPath="url(#band-home)" />
          <path d={d} className={styles.bandAway} clipPath="url(#band-away)" />
        </g>
      ))}
    </svg>
  );
}

export interface BandTeams {
  metaId: string; // the match_meta event the team names come from
  teams: MatchDetail["teams"];
}

/** What the band is: the metric's own label (it names its window) and which side is which. The band
 * writes no value. Marks match the score bug (home: filled circle, away: ring) next to each team name,
 * plus an arrow, so the side never rests on colour. */
export function BandKey({ series, teams }: { series: Series; teams: BandTeams | null }) {
  return (
    <p className={styles.bandKey} data-testid="band-key">
      <span className={styles.bandLabel} title={series.definition}>
        {series.label}
      </span>
      {teams
        ? (["home", "away"] as const).map((side) => (
            <span key={side} className={styles.bandSide} data-side={side}>
              <span className={styles.bandMark} data-mark={side === "home" ? "dot" : "ring"} aria-hidden="true" />
              <Fact event={{ id: teams.metaId, team: side }} field="team" teams={teams.teams} />
              <span aria-hidden="true">{side === "home" ? "↑" : "↓"}</span>
              <span className={styles.visuallyHidden}>{side === "home" ? "above the line" : "below the line"}</span>
            </span>
          ))
        : null}
    </p>
  );
}
