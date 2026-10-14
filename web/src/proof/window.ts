// What the Receipt says about a claim's window. The kind and length come from /api/metrics; the minutes
// are the claim's own labels. Returned as a structure so the numbers can be drawn by <Fact>.
import type { Claim, MetricInfo } from "../api/types";

export type WindowText =
  | { kind: "at"; end: string }
  | { kind: "range" }
  | { kind: "rolling" }
  | { kind: "unknown" };

export function windowKind(claim: Pick<Claim, "start" | "end">, info: MetricInfo | undefined): WindowText {
  if (!info) return { kind: "unknown" };
  if (info.window.type === "rolling") return { kind: "rolling" };
  if (info.window.type === "claim_range") {
    return claim.start === claim.end ? { kind: "at", end: claim.end } : { kind: "range" };
  }
  return { kind: "unknown" };
}
