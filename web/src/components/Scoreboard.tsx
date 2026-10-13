import type { Score, Teams } from "../types";

export function Scoreboard({ teams, score, minute }: { teams: Teams; score: Score; minute: string }) {
  return (
    <section className="scoreboard" aria-label="Score">
      <span className="side home">{teams.home}</span>
      <span className="score" aria-live="polite">
        {score.home}–{score.away}
      </span>
      <span className="side away">{teams.away}</span>
      <span className="clock" aria-label="Minute">
        {minute}
      </span>
    </section>
  );
}
