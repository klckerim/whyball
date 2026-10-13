import type { Claim, Moment } from "./types";

/** A piece of card text; `claimId` marks a value the code rendered from that claim. */
export interface Segment {
  text: string;
  claimId?: string;
}

interface Span {
  start: number;
  end: number;
  claimId: string;
}

// Metrics whose value the narration states in words ("scored", "sent off", "drew level"), so a bare
// number in the sentence is never theirs.
const WORDED_METRICS = new Set(["goals", "red_cards", "score_margin"]);

const isDigit = (ch: string | undefined) => ch !== undefined && ch >= "0" && ch <= "9";
const isLetter = (ch: string | undefined) => ch !== undefined && /\p{L}/u.test(ch);

/**
 * Finds the code-rendered values of a card's claims in its text: the score pair, player names,
 * distinctive values (percentages, signed decimals), bare counts in claim order, and the claim's
 * minute labels. A heuristic over the published sentence (the store keeps no slot spans); a claim
 * it cannot place stays unmarked and is still listed in the evidence panel.
 */
export function markClaims(text: string, claims: Claim[]): Segment[] {
  const spans: Span[] = [];
  const free = (s: number, e: number) => spans.every((x) => e <= x.start || s >= x.end);

  const numberOk = (s: number, e: number) =>
    !isDigit(text[s - 1]) && text[s - 1] !== "." && !isDigit(text[e]) && !/[.,]\d/.test(text.slice(e, e + 2)) && text[e] !== "%" && text[e] !== "'";
  const wordOk = (s: number, e: number) => !isLetter(text[s - 1]) && !isLetter(text[e]);
  const minuteOk = (s: number) => !isDigit(text[s - 1]) && text[s - 1] !== "+";

  const find = (needle: string, from: number, ok: (s: number, e: number) => boolean): number => {
    if (!needle) return -1;
    for (let i = text.indexOf(needle, from); i !== -1; i = text.indexOf(needle, i + 1)) {
      if (ok(i, i + needle.length) && free(i, i + needle.length)) return i;
    }
    return -1;
  };
  const mark = (start: number, len: number, claimId: string) => spans.push({ start, end: start + len, claimId });

  // 1. The score pair "1–2" (score claims for home and away).
  const home = claims.find((c) => c.metric === "score" && c.team === "home");
  const away = claims.find((c) => c.metric === "score" && c.team === "away");
  if (home && away) {
    for (const dash of ["–", "-"]) {
      const pair = `${home.display}${dash}${away.display}`;
      const i = find(pair, 0, numberOk);
      if (i !== -1) {
        mark(i, home.display.length, home.id);
        mark(i + home.display.length + dash.length, away.display.length, away.id);
        break;
      }
    }
  }
  const placed = (c: Claim) => spans.some((s) => s.claimId === c.id);

  // 2. Player names.
  for (const c of claims) {
    if (!c.player) continue;
    const i = find(c.player, 0, wordOk);
    if (i !== -1) mark(i, c.player.length, c.id);
  }

  // 3. Distinctive values ("55%", "+0.75"), then 4. bare counts in claim order.
  for (const c of claims) {
    if (placed(c) || /^\d+$/.test(c.display)) continue;
    const i = find(c.display, 0, numberOk);
    if (i !== -1) mark(i, c.display.length, c.id);
  }
  let cursor = 0;
  for (const c of claims) {
    if (placed(c) || !/^\d+$/.test(c.display) || WORDED_METRICS.has(c.metric)) continue;
    const i = find(c.display, cursor, numberOk);
    if (i !== -1) {
      mark(i, c.display.length, c.id);
      cursor = i + c.display.length;
    }
  }

  // 5. Minute labels: the first claim whose window starts or ends there.
  for (const c of claims) {
    for (const label of new Set([c.end, c.start])) {
      if (!label || label === "0'") continue;
      const i = find(label, 0, minuteOk);
      if (i !== -1) mark(i, label.length, c.id);
    }
  }

  spans.sort((a, b) => a.start - b.start);
  const out: Segment[] = [];
  let at = 0;
  for (const s of spans) {
    if (s.start > at) out.push({ text: text.slice(at, s.start) });
    out.push({ text: text.slice(s.start, s.end), claimId: s.claimId });
    at = s.end;
  }
  if (at < text.length) out.push({ text: text.slice(at) });
  return out;
}

/** The claim shown first for a card: the first one backed by events. */
export function defaultClaim(m: Moment): Claim | null {
  return m.claims.find((c) => c.evidence.length > 0) ?? m.claims[0] ?? null;
}
