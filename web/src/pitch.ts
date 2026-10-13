/** Pitch geometry for the evidence view. Event coordinates are metres on a 105×68 pitch
 * (app/generator/models.py: x 0..105, the home team attacks towards x=105; y 0..68). */

export const PITCH = { w: 105, h: 68, pad: 3 } as const;

export const VIEWBOX = `0 0 ${PITCH.w + 2 * PITCH.pad} ${PITCH.h + 2 * PITCH.pad}`;

const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));

/** Event position → SVG user units: shifted by the padding, y flipped so y=0 is the bottom
 * touchline, clamped to the pitch. Null when the event has no position (cards, substitutions). */
export function toPitch(x: number | null | undefined, y: number | null | undefined): { cx: number; cy: number } | null {
  if (x == null || y == null || !Number.isFinite(x) || !Number.isFinite(y)) return null;
  return {
    cx: PITCH.pad + clamp(x, 0, PITCH.w),
    cy: PITCH.pad + (PITCH.h - clamp(y, 0, PITCH.h)),
  };
}

export interface PitchPoint {
  id: string;
  cx: number;
  cy: number;
}

/** Points that sit on (almost) the same spot are fanned out on a small ring of radius `r`, so every
 * event stays visible and clickable (restarts from the centre spot share one position). */
export function spreadOverlaps<T extends PitchPoint>(points: T[], r = 2, eps = 0.5): T[] {
  const groups: T[][] = [];
  for (const p of points) {
    const g = groups.find((g) => Math.hypot(g[0].cx - p.cx, g[0].cy - p.cy) < eps);
    if (g) g.push(p);
    else groups.push([p]);
  }
  const moved = new Map<string, { cx: number; cy: number }>();
  for (const g of groups) {
    if (g.length < 2) continue;
    g.forEach((p, i) => {
      const a = (2 * Math.PI * i) / g.length - Math.PI / 2;
      moved.set(p.id, { cx: g[0].cx + r * Math.cos(a), cy: g[0].cy + r * Math.sin(a) });
    });
  }
  return points.map((p) => (moved.has(p.id) ? { ...p, ...moved.get(p.id)! } : p));
}
