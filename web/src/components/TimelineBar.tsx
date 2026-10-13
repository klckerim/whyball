import { useEffect, useRef, useState } from "react";

import { assignLanes, clockLabel, fraction, SPEED_OPTIONS, typeLabel } from "../timeline";
import type { Moment, Period } from "../types";
import { TypeIcon } from "./TypeIcon";

export const SPEEDS = SPEED_OPTIONS.map((s) => s.value);

const MARKER_PX = 18; // marker box + gap: markers closer than this share no lane
const LANE_PX = 20;

interface Props {
  t: number;
  duration: number;
  periods: Period[];
  moments: Moment[];
  playing: boolean;
  speed: number;
  selectedId: string | null;
  onPlay: () => void;
  onPause: () => void;
  onRestart: () => void;
  onSeek: (t: number) => void;
  onSpeed: (speed: number) => void;
  onMarker: (m: Moment) => void;
}

function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width || fallback));
    ro.observe(el);
    return () => ro.disconnect();
  }, [fallback]);
  return [ref, width] as const;
}

export function TimelineBar(p: Props) {
  const half = p.periods.find((x) => x.period === 2);
  const [trackRef, width] = useWidth<HTMLDivElement>(800);
  const at = (t: number) => `${fraction(t, p.duration) * 100}%`;
  const lanes = assignLanes(
    p.moments.map((m) => ({ id: m.id, f: fraction(m.t, p.duration) })),
    MARKER_PX / Math.max(width, 1),
  );
  const laneCount = Math.max(1, ...[...lanes.values()].map((l) => l + 1));
  const types = [...new Set(p.moments.map((m) => m.type))];

  return (
    <section className="timeline panel" aria-label="Match timeline">
      <div className="controls">
        <button
          type="button"
          className="btn play"
          onClick={p.playing ? p.onPause : p.onPlay}
          aria-label={p.playing ? "Pause" : "Play"}
          aria-keyshortcuts="Space K"
          title={`${p.playing ? "Pause" : "Play"} (Space or K)`}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
            {p.playing ? (
              <path fill="currentColor" d="M3 2h3v10H3zM8 2h3v10H8z" />
            ) : (
              <path fill="currentColor" d="M3.5 1.8 12 7l-8.5 5.2z" />
            )}
          </svg>
        </button>
        <button type="button" className="btn primary" onClick={p.onRestart}>
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" focusable="false">
            <path
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              d="M2.5 7a4.5 4.5 0 1 0 1.4-3.3M2.5 1.8v2.4h2.4"
            />
          </svg>
          Replay from kickoff
        </button>
        <fieldset className="speed">
          <legend className="visually-hidden">Playback speed</legend>
          {SPEED_OPTIONS.map((s) => (
            <label key={s.value} title={s.title}>
              <input
                type="radio"
                name="speed"
                value={s.value}
                checked={p.speed === s.value}
                onChange={() => p.onSpeed(s.value)}
              />
              <span>{s.label}</span>
            </label>
          ))}
        </fieldset>
      </div>

      <div className="track-area" ref={trackRef}>
        <div className="markers" style={{ height: laneCount * LANE_PX }}>
          {p.moments.map((m) => {
            const tip = `${m.minute_label} · ${typeLabel(m.type)}`;
            return (
              <button
                key={m.id}
                type="button"
                className={`marker type-${m.type}${m.t <= p.t ? " passed" : ""}${m.id === p.selectedId ? " current" : ""}`}
                style={{ left: at(m.t), bottom: (lanes.get(m.id) ?? 0) * LANE_PX }}
                aria-label={tip}
                data-tip={tip}
                onClick={() => p.onMarker(m)}
              >
                <TypeIcon type={m.type} size={14} />
              </button>
            );
          })}
        </div>
        <div className="track">
          <div className="fill" style={{ width: at(p.t) }} />
          {half && <span className="half-line" style={{ left: at(half.start_t) }} />}
          <span className="knob" style={{ left: at(p.t) }} />
          <input
            className="scrub"
            type="range"
            min={0}
            max={p.duration}
            step={1}
            value={p.t}
            onChange={(e) => p.onSeek(Number(e.target.value))}
            aria-label="Match minute"
            aria-valuetext={clockLabel(p.t, p.periods)}
          />
        </div>
        <div className="ticks" aria-hidden="true">
          <span style={{ left: 0 }}>KO</span>
          {half && (
            <span className="ht" style={{ left: at(half.start_t) }}>
              HT
            </span>
          )}
          <span style={{ right: 0 }}>FT</span>
        </div>
      </div>

      {types.length > 0 && (
        <ul className="legend" aria-label="Marker legend">
          {types.map((type) => (
            <li key={type} className={`type-${type}`}>
              <TypeIcon type={type} size={10} />
              <span>{typeLabel(type)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
