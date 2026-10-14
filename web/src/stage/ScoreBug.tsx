// Score bug: both team names always shown with their mark (home: filled circle, away: ring), so the
// sides never depend on colour. Names come from the match_meta event, score and clock from the event
// in effect at t (its own fields), all through <Fact>.
import type { MatchDetail, TimelineEvent } from "../api/types";
import { eventId, Fact, NO_DATA } from "../design/Fact";
import styles from "./stage.module.css";

interface Props {
  detail: Pick<MatchDetail, "event_match_id" | "teams">;
  meta: TimelineEvent; // the match_meta event (seq 0)
  current: TimelineEvent | null; // eventAt(t)
  ended: boolean;
}

export function ScoreBug({ detail, meta, current, ended }: Props) {
  const metaId = eventId(detail.event_match_id, meta.seq);
  const now = current ? { ...current, id: eventId(detail.event_match_id, current.seq) } : null;
  return (
    <div className={styles.bug} role="group" aria-label="Score">
      {(["home", "away"] as const).map((side) => (
        <div key={side} className={styles.bugRow} data-side={side}>
          <span className={styles.teamMark} data-mark={side === "home" ? "dot" : "ring"} aria-hidden="true" />
          <Fact className={styles.teamName} event={{ id: metaId, team: side }} field="team" teams={detail.teams} />
          {now ? (
            <Fact className={styles.score} event={now} field={side === "home" ? "score_home" : "score_away"} />
          ) : (
            <span className={styles.score}>{NO_DATA}</span>
          )}
        </div>
      ))}
      <div className={styles.clock}>
        {now ? <Fact event={now} field="minute_label" /> : null}
        {ended ? <span className={styles.ft}>FT</span> : null}
      </div>
    </div>
  );
}
