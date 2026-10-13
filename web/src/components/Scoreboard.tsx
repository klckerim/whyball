import { teamInitials } from "../timeline";
import type { Score, Side, Teams } from "../types";

/** Coloured circle with the club's initials (synthetic clubs have no crest). */
export function Crest({ side, name, size = "md" }: { side: Side; name: string; size?: "sm" | "md" }) {
  return (
    <span className={`crest crest-${side} crest-${size}`} aria-hidden="true">
      {teamInitials(name)}
    </span>
  );
}

export function Scoreboard({ teams, score, minute }: { teams: Teams; score: Score; minute: string }) {
  return (
    <section className="scoreboard" aria-label="Score">
      <div className="team home">
        <Crest side="home" name={teams.home} />
        <span className="team-name">{teams.home}</span>
      </div>
      <div className="score-block">
        <span className="score" aria-live="polite" aria-label={`${teams.home} ${score.home}, ${teams.away} ${score.away}`}>
          <span>{score.home}</span>
          <span className="dash" aria-hidden="true">
            –
          </span>
          <span>{score.away}</span>
        </span>
        <span className="clock" aria-label={minute === "FT" ? "Full time" : `Minute ${minute}`}>
          {minute}
        </span>
      </div>
      <div className="team away">
        <Crest side="away" name={teams.away} />
        <span className="team-name">{teams.away}</span>
      </div>
    </section>
  );
}
