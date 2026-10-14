// Abstract pitch (our own drawing, 105×68 like the event coordinates; markings approximate, not a
// regulation plan). Only the ball: a marker at the last positioned event, a straight-line move to the
// next one (visual only) and a short trail. No player dots, formations or heat maps (UI_SPEC §2).
import { PitchSurface, toSvg } from "../design/PitchSurface";
import type { BallPoint } from "../state/match";
import styles from "./stage.module.css";

export { PITCH, toSvg } from "../design/PitchSurface";

export function Pitch({ ball, trail }: { ball: BallPoint | null; trail: BallPoint[] }) {
  const pts = [...trail, ...(ball ? [ball] : [])].map(toSvg);
  const b = ball ? toSvg(ball) : null;
  const hasTrail = pts.length > 1; // a line needs two points
  return (
    <div className={styles.pitchBox}>
      <PitchSurface
        svgClassName={styles.pitch}
        linesClassName={styles.lines}
        label={b ? "Ball position on the pitch" : "Pitch, no ball location yet"}
      >
        {hasTrail ? (
          <polyline className={styles.trail} points={pts.map((p) => `${p.cx},${p.cy}`).join(" ")} data-testid="trail" />
        ) : null}
        {b ? <circle className={styles.ball} cx={b.cx} cy={b.cy} r="1.4" data-testid="ball" data-seq={ball!.seq} /> : null}
      </PitchSurface>
      {b ? null : <p className={styles.noLocation}>no location</p>}
      <p className={styles.feedNote}>synthetic feed visualization</p>
    </div>
  );
}
