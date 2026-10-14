// Match timeline: a slider over the match clock (click, drag or keys to seek), the half-time mark, a
// glyph button per narrated moment at its time, and the pressure band behind. Text labels only; the
// current minute comes from the event in effect.
import { useRef } from "react";

import type { Moment, Period, Series } from "../api/types";
import { TypeGlyph, typeLabel } from "../design/TypeGlyph";
import styles from "./app.module.css";
import { type BandTeams, BandKey, PressureBand } from "./PressureBand";

/** Keyboard seek steps in match seconds (design parameters, DESIGN D19). */
export const SEEK = { step: 30, page: 300 } as const;

export function timeAtX(clientX: number, rect: { left: number; width: number }, duration: number): number {
  if (rect.width <= 0) return 0;
  return Math.round(Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)) * duration);
}

const pct = (t: number, duration: number) => `${duration > 0 ? (t / duration) * 100 : 0}%`;

interface Props {
  t: number;
  duration: number;
  periods: Period[];
  moments: Moment[];
  series: Series | null;
  bandTeams?: BandTeams | null;
  minuteLabel: string; // of the event in effect, for the slider's spoken value
  shownId: string | null;
  onSeek: (t: number) => void;
  onMoment: (id: string) => void;
}

export function Timeline({ t, duration, periods, moments, series, bandTeams = null, minuteLabel, shownId, onSeek, onMoment }: Props) {
  const track = useRef<HTMLDivElement>(null);
  const seekTo = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect();
    if (rect) onSeek(timeAtX(clientX, rect, duration));
  };
  const second = periods.find((p) => p.period === 2); // its start is the half-time mark
  const keys: Record<string, number> = {
    ArrowLeft: t - SEEK.step,
    ArrowRight: t + SEEK.step,
    PageDown: t - SEEK.page,
    PageUp: t + SEEK.page,
    Home: 0,
    End: duration,
  };

  return (
    <div className={styles.timeline}>
      <div
        ref={track}
        className={styles.track}
        role="slider"
        tabIndex={0}
        aria-label="Match time"
        aria-valuemin={0}
        aria-valuemax={duration}
        aria-valuenow={Math.round(t)}
        aria-valuetext={minuteLabel}
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture?.(e.pointerId);
          seekTo(e.clientX);
        }}
        onPointerMove={(e) => {
          if (e.currentTarget.hasPointerCapture?.(e.pointerId)) seekTo(e.clientX);
        }}
        onKeyDown={(e) => {
          if (!(e.key in keys)) return;
          e.preventDefault();
          onSeek(Math.min(duration, Math.max(0, keys[e.key]!)));
        }}
      >
        {series ? <PressureBand series={series} duration={duration} /> : null}
        <div className={styles.axis} aria-hidden="true" />
        {second ? (
          <div className={styles.half} style={{ left: pct(second.start_t, duration) }} aria-hidden="true">
            <span>HT</span>
          </div>
        ) : null}
        <div className={styles.playhead} style={{ left: pct(t, duration) }} aria-hidden="true" />
      </div>
      <div className={styles.markers}>
        {moments.map((m) => (
          <button
            key={m.id}
            type="button"
            className={styles.marker}
            style={{ left: pct(m.t, duration) }}
            aria-label={`${typeLabel(m.type)}, ${m.minute_label}`}
            aria-current={m.id === shownId ? "true" : undefined}
            data-source={m.source}
            onClick={() => onMoment(m.id)}
          >
            <TypeGlyph type={m.type} />
          </button>
        ))}
      </div>
      <div className={styles.ends} aria-hidden="true">
        <span>Kick-off</span>
        <span>Full time</span>
      </div>
      {series ? <BandKey series={series} teams={bandTeams} /> : null}
    </div>
  );
}
