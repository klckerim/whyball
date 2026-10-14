// Moments of the match in time order: minute, type glyph and label, source badge. A listbox with a
// roving tab stop; the arrow keys, Home and End move the selection (both axes: the rail turns into a
// horizontal strip on narrow screens).
import { useRef } from "react";

import type { Moment } from "../api/types";
import { eventId, Fact } from "../design/Fact";
import { SourceBadge } from "../design/SourceBadge";
import { TypeGlyph, typeLabel } from "../design/TypeGlyph";
import styles from "./proof.module.css";

interface Props {
  moments: readonly Moment[];
  eventMatchId: string;
  selectedId: string | null;
  horizontal: boolean;
  onSelect: (id: string) => void;
}

export function nextIndex(key: string, i: number, n: number): number | null {
  if (n === 0) return null;
  switch (key) {
    case "ArrowDown":
    case "ArrowRight":
      return Math.min(n - 1, i + 1);
    case "ArrowUp":
    case "ArrowLeft":
      return Math.max(0, i - 1);
    case "Home":
      return 0;
    case "End":
      return n - 1;
    default:
      return null;
  }
}

export function MomentRail({ moments, eventMatchId, selectedId, horizontal, onSelect }: Props) {
  const refs = useRef<(HTMLLIElement | null)[]>([]);
  const current = Math.max(0, moments.findIndex((m) => m.id === selectedId));
  return (
    <ul
      className={styles.rail}
      role="listbox"
      aria-label="Narrated moments"
      aria-orientation={horizontal ? "horizontal" : "vertical"}
    >
      {moments.map((m, i) => {
        const selected = m.id === selectedId;
        return (
          <li
            key={m.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            role="option"
            aria-selected={selected}
            tabIndex={i === current ? 0 : -1}
            className={styles.railItem}
            data-moment-id={m.id}
            onClick={() => onSelect(m.id)}
            onKeyDown={(e) => {
              const to = nextIndex(e.key, i, moments.length);
              if (to === null) return;
              e.preventDefault();
              onSelect(moments[to]!.id);
              refs.current[to]?.focus();
            }}
          >
            <Fact
              className={styles.railMinute}
              event={{ id: eventId(eventMatchId, m.at_seq), minute_label: m.minute_label }}
              field="minute_label"
            />
            <span className={styles.railType}>
              <TypeGlyph type={m.type} />
              <span>{typeLabel(m.type)}</span>
            </span>
            <SourceBadge source={m.source} />
          </li>
        );
      })}
    </ul>
  );
}
