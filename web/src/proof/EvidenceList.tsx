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
  selectedEventId: string | null;
  onSelect: (id: string) => void;
}

export function EvidenceList({ rows, teams, selectedEventId, onSelect }: Props) {
  if (rows.length === 0) return <p className={styles.note}>This claim counts no events in its window.</p>;
  return (
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
  );
}
