// The pitch with the evidence of the selected claim marked (shape by event type, selected event
// ringed) and the other claims' events of the card dimmed. The position is the BALL's at the event,
// not a player's. An event without a position is not drawn; the list says "no location".
import { PitchSurface, toSvg } from "../design/PitchSurface";
import type { EvidenceRow } from "./evidence";
import { EventGlyph, EventMark, eventLabel } from "./eventMark";
import styles from "./proof.module.css";

const MIN_PATH = 2;

interface Props {
  marked: readonly EvidenceRow[];
  dimmed: readonly EvidenceRow[];
  selectedEventId: string | null;
  onSelect: (id: string) => void;
}

export function EvidencePitch({ marked, dimmed, selectedEventId, onSelect }: Props) {
  const shown = marked.filter((r) => r.at);
  const dimmedShown = dimmed.filter((r) => r.at && !marked.some((m) => m.id === r.id));
  const noneLocated = shown.length === 0;
  const hasPath = shown.length >= MIN_PATH; // a motion line needs two marks
  const types = [...new Set(shown.map((r) => r.type))];
  return (
    <figure className={styles.pitchFig}>
      <PitchSurface
        svgClassName={styles.pitch}
        linesClassName={styles.pitchLines}
        label="Evidence events on the pitch, at the ball position of each event"
      >
        {dimmedShown.map((r) => (
          <EventMark key={r.id} type={r.type} {...toSvg(r.at!)} scale={1.3} state="dim" />
        ))}
        {hasPath ? (
          <polyline className={styles.motion} points={shown.map((r) => `${toSvg(r.at!).cx},${toSvg(r.at!).cy}`).join(" ")} aria-hidden="true" />
        ) : null}
        {shown.map((r) => (
          <EventMark
            key={r.id}
            type={r.type}
            {...toSvg(r.at!)}
            scale={r.id === selectedEventId ? 2.4 : 1.9}
            state={r.id === selectedEventId ? "selected" : "marked"}
            onSelect={() => onSelect(r.id)}
          />
        ))}
      </PitchSurface>
      <figcaption className={styles.pitchCaption}>
        <span>ball position at each event</span>
        {noneLocated ? <span>no located event for this claim</span> : null}
        <ul className={styles.legend} aria-label="Event shapes">
          {types.map((t) => (
            <li key={t}>
              <EventGlyph type={t} />
              {eventLabel(t)}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
