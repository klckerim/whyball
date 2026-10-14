// The Flip between On Air and Proof (DESIGN D27): the face turns edge-on and the other turns in.
// `shown` is the face to draw now; `phase` drives the CSS. Reduced motion: no turn, `shown` follows at once.
import { useEffect, useState } from "react";

export type Mode = "air" | "proof";

/** Out + in = 380 ms, within the 400 ms transition cap (UI_SPEC B3). */
export const FLIP_MS = { out: 180, in: 200 } as const;

export function useFlip(mode: Mode, reduced: boolean): { shown: Mode; phase: "idle" | "out" | "in" } {
  const [shown, setShown] = useState<Mode>(mode);
  const [phase, setPhase] = useState<"idle" | "out" | "in">("idle");
  useEffect(() => {
    if (mode === shown) return;
    if (reduced) {
      setShown(mode);
      setPhase("idle");
      return;
    }
    setPhase("out");
    const swap = setTimeout(() => {
      setShown(mode);
      setPhase("in");
    }, FLIP_MS.out);
    return () => clearTimeout(swap);
  }, [mode, shown, reduced]);
  useEffect(() => {
    if (phase !== "in") return;
    const done = setTimeout(() => setPhase("idle"), FLIP_MS.in);
    return () => clearTimeout(done);
  }, [phase]);
  return { shown, phase };
}
