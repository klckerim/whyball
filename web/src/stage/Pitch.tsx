// Abstract pitch (our own drawing, 105×68 like the event coordinates; markings approximate, not a
// regulation plan). Only the ball: a marker at the last positioned event, a straight-line move to the
// next one (visual only) and a short trail. No player dots, formations or heat maps (UI_SPEC §2).
import type { BallPoint } from "../state/match";
import styles from "./stage.module.css";

export const PITCH = { w: 105, h: 68 } as const;

/** Event coordinates → SVG: y flipped so y=0 is the bottom touchline. */
export function toSvg(p: { x: number; y: number }): { cx: number; cy: number } {
  return { cx: p.x, cy: PITCH.h - p.y };
}

export function Pitch({ ball, trail }: { ball: BallPoint | null; trail: BallPoint[] }) {
  const pts = [...trail, ...(ball ? [ball] : [])].map(toSvg);
  const b = ball ? toSvg(ball) : null;
  const hasTrail = pts.length > 1; // a line needs two points
  return (
    <div className={styles.pitchBox}>
      <svg
        className={styles.pitch}
        viewBox={`0 0 ${PITCH.w} ${PITCH.h}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={b ? "Ball position on the pitch" : "Pitch, no ball location yet"}
      >
        <g className={styles.lines}>
          <rect x="0" y="0" width={PITCH.w} height={PITCH.h} />
          <line x1={PITCH.w / 2} y1="0" x2={PITCH.w / 2} y2={PITCH.h} />
          <circle cx={PITCH.w / 2} cy={PITCH.h / 2} r="9" />
          <rect x="0" y="14" width="16" height="40" />
          <rect x={PITCH.w - 16} y="14" width="16" height="40" />
          <rect x="0" y="25" width="5" height="18" />
          <rect x={PITCH.w - 5} y="25" width="5" height="18" />
        </g>
        {hasTrail ? (
          <polyline className={styles.trail} points={pts.map((p) => `${p.cx},${p.cy}`).join(" ")} data-testid="trail" />
        ) : null}
        {b ? <circle className={styles.ball} cx={b.cx} cy={b.cy} r="1.4" data-testid="ball" data-seq={ball!.seq} /> : null}
      </svg>
      {b ? null : <p className={styles.noLocation}>no location</p>}
      <p className={styles.feedNote}>synthetic feed visualization</p>
    </div>
  );
}
