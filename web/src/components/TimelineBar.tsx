import { clockLabel, fraction, typeLabel } from "../timeline";
import type { Moment, Period } from "../types";

export const SPEEDS = [30, 60, 120, 300];

interface Props {
  t: number;
  duration: number;
  periods: Period[];
  moments: Moment[];
  playing: boolean;
  speed: number;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (t: number) => void;
  onSpeed: (speed: number) => void;
}

export function TimelineBar(p: Props) {
  const half = p.periods.find((x) => x.period === 2);
  return (
    <section className="timeline" aria-label="Match timeline">
      <button
        type="button"
        className="play"
        onClick={p.playing ? p.onPause : p.onPlay}
        aria-label={p.playing ? "Pause" : "Play"}
      >
        {p.playing ? "❚❚" : "▶"}
      </button>
      <div className="track">
        <input
          type="range"
          min={0}
          max={p.duration}
          step={1}
          value={p.t}
          onChange={(e) => p.onSeek(Number(e.target.value))}
          aria-label="Match minute"
          aria-valuetext={clockLabel(p.t, p.periods)}
        />
        <div className="markers" aria-hidden="true">
          {half && <span className="half" style={{ left: `${fraction(half.start_t, p.duration) * 100}%` }} />}
          {p.moments.map((m) => (
            <span
              key={m.id}
              className={`marker type-${m.type}${m.t <= p.t ? " passed" : ""}`}
              style={{ left: `${fraction(m.t, p.duration) * 100}%` }}
              title={`${m.minute_label} ${typeLabel(m.type)}`}
            />
          ))}
        </div>
      </div>
      <label className="speed">
        <span className="visually-hidden">Speed</span>
        <select value={p.speed} onChange={(e) => p.onSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => (
            <option key={s} value={s}>
              {s}×
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}
