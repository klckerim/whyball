// Transport: play/pause, previous/next moment, speed, and the timeline.
import * as ToggleGroup from "@radix-ui/react-toggle-group";

import type { Moment, Period, Series } from "../api/types";
import { SPEEDS, wallSeconds } from "../state/clock";
import styles from "./app.module.css";
import type { BandTeams } from "./PressureBand";
import { Timeline } from "./Timeline";

interface Props {
  t: number;
  duration: number;
  playing: boolean;
  speed: number;
  periods: Period[];
  moments: Moment[];
  series: Series | null;
  bandTeams?: BandTeams | null;
  minuteLabel: string;
  shownId: string | null;
  canPrev: boolean;
  canNext: boolean;
  onToggle: () => void;
  onSpeed: (speed: number) => void;
  onPrev: () => void;
  onNext: () => void;
  onSeek: (t: number) => void;
  onMoment: (id: string) => void;
}

export function Transport(p: Props) {
  const current = SPEEDS.find((s) => s.speed === p.speed) ?? SPEEDS[0];
  return (
    <div className={styles.transport}>
      <div className={styles.controls}>
        <button type="button" className={styles.button} onClick={p.onPrev} disabled={!p.canPrev} aria-label="Previous moment">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 3v10M13 3 6 8l7 5Z" fill="currentColor" stroke="currentColor" strokeWidth="1.5" /></svg>
        </button>
        <button type="button" className={`${styles.button} ${styles.play}`} onClick={p.onToggle} aria-label={p.playing ? "Pause" : "Play"}>
          {p.playing ? (
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 3h3v10H4zM9 3h3v10H9z" fill="currentColor" /></svg>
          ) : (
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5 13.5 8 4 13.5Z" fill="currentColor" /></svg>
          )}
        </button>
        <button type="button" className={styles.button} onClick={p.onNext} disabled={!p.canNext} aria-label="Next moment">
          <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M12 3v10M3 3l7 5-7 5Z" fill="currentColor" stroke="currentColor" strokeWidth="1.5" /></svg>
        </button>
        <ToggleGroup.Root
          type="single"
          className={styles.speeds}
          value={current.id}
          onValueChange={(id) => {
            const s = SPEEDS.find((x) => x.id === id);
            if (s) p.onSpeed(s.speed);
          }}
          aria-label="Replay speed"
        >
          {SPEEDS.map((s) => (
            <ToggleGroup.Item key={s.id} value={s.id} className={styles.speed}>
              {s.label}
            </ToggleGroup.Item>
          ))}
        </ToggleGroup.Root>
        <span className={styles.speedHint}>
          whole match in about {wallSeconds(p.duration, current.speed)} s
        </span>
      </div>
      <Timeline
        t={p.t}
        duration={p.duration}
        periods={p.periods}
        moments={p.moments}
        series={p.series}
        bandTeams={p.bandTeams}
        minuteLabel={p.minuteLabel}
        shownId={p.shownId}
        onSeek={p.onSeek}
        onMoment={p.onMoment}
      />
    </div>
  );
}
