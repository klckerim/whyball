// EBU R 095 v1.1 safe areas, per edge (docs/DESIGN.md D1). The only place these values live.
export const SAFE_AREA = {
  graphics: 0.05, // graphics-safe: every graphic stays inside
  action: 0.035, // action-safe: critical action stays inside
} as const;

export type SafeKind = keyof typeof SAFE_AREA;

/** CSS inset for an absolutely positioned box in the 16:9 frame (percent of width/height per edge). */
export function safeInset(kind: SafeKind): string {
  return `${SAFE_AREA[kind] * 100}%`;
}
