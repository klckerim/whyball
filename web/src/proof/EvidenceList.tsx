// The events behind the selected claim: minute, type, player, team, outcome, and whether the ball
// position is known. Every value is a <Fact> tied to its event. The selected event is marked here and
// on the pitch.
import type { MatchDetail } from "../api/types";
import { Fact } from "../design/Fact";
import type { EvidenceRow } from "./evidence";
import { EventGlyph, eventLabel } from "./eventMark";
import styles from "./proof.module.css";

interface Props {
  rows: readonly EvidenceRow[];
  teams: MatchDetail["teams"];
  /** The selected claim's value aggregates a whole window (ratio or rolling). */
  aggregate: boolean;
  selectedEventId: string | null;
  onSelect: (id: string) => void;
}

export function EvidenceList({ rows, teams, aggregate, selectedEventId, onSelect }: Props) {
  const empty = rows.length === 0;
  return (
    <section className={styles.cited} aria-label="Events cited by this card">
      <h3 className={styles.h3}>Events cited by this card</h3>
      {aggregate ? (
        <p className={styles.note} data-testid="aggregate-note">
          This value aggregates all events in its window; the list shows only the events this card cites.
        </p>
      ) : null}
      {empty ? <p className={styles.note}>This card cites no events for this claim.</p> : null}
      {empty ? null : (
      <ol className={styles.events} aria-label="Evidence events">
        {rows.map((r) => (
          <li key={r.id}>
            <button type="button" className={styles.eventRow} aria-pressed={r.id === selectedEventId} onClick={() => onSelect(r.id)}>
              <Fact className={styles.evMinute} event={r} field="minute_label" />
              <span className={styles.evType}>
                <EventGlyph type={r.type} />
                {eventLabel(r.type)}
              </span>
              <Fact className={styles.evPlayer} event={r} field="player" missing="no player" />
              <Fact className={styles.evTeam} event={r} field="team" teams={teams} missing="no team" />
              <Fact className={styles.evOutcome} event={r} field="outcome" missing="no outcome" />
              {r.at ? null : <span className={styles.noLocation}>no location</span>}
            </button>
          </li>
        ))}
      </ol>
      )}
    </section>
  );
}
