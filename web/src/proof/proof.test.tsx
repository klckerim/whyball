import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Moment } from "../api/types";
import { matchFixtures, metricsFixture, type MatchFixture } from "../test/fixtures";
import { nextIndex } from "./MomentRail";
import { ProofView } from "./ProofView";
import type { MetricsState } from "./Receipt";
import { joinEvidence, rowsOf } from "./evidence";
import { windowKind } from "./window";

afterEach(cleanup);

const ok: MetricsState = { status: "ok", data: metricsFixture, retry: () => {} };
const red = matchFixtures.find((m) => m.summary.id === "red_card_swing_seed42")!;

function Harness({ fx, metrics = ok, start }: { fx: MatchFixture; metrics?: MetricsState; start?: string }) {
  const [id, setId] = useState<string | null>(start ?? fx.moments[0]?.id ?? null);
  return <ProofView detail={fx.detail} moments={fx.moments} events={fx.events} metrics={metrics} momentId={id} onMoment={setId} />;
}

const receipt = () => screen.getByRole("region", { name: "Receipt" });
const claimDetail = () => screen.getByRole("region", { name: "Selected claim" });

describe("T2 over every fixture card and claim", () => {
  it("draws every segment claim as a Fact, selects every claim, lists its evidence by event id", () => {
    let claims = 0;
    let inSentence = 0;
    let inWords = 0;
    let unplaceable = 0;
    const metricsWithoutValue = new Map<string, number>();
    for (const fx of matchFixtures) {
      for (const moment of fx.moments) {
        const { unmount } = render(<Harness fx={fx} start={moment.id} />);
        const sentence = receipt().querySelector("p")!;
        expect(sentence.textContent).toBe(moment.text);
        const shown = [...sentence.querySelectorAll("[data-claim-id]")].map((el) => [el.getAttribute("data-claim-id"), el.textContent]);
        expect(shown).toEqual(moment.segments.filter((s) => s.claim_id).map((s) => [s.claim_id, s.text]));
        for (const claim of moment.claims) {
          claims++;
          const inText = shown.some(([id]) => id === claim.id);
          const button = inText
            ? [...sentence.querySelectorAll("button")].find((b) => b.querySelector(`[data-claim-id="${claim.id}"]`))
            : [...receipt().querySelectorAll("button")].find((b) => b.querySelector(`[data-claim-id="${claim.id}"]`));
          if (!button) {
            unplaceable++;
            continue;
          }
          if (inText) inSentence++;
          else {
            inWords++;
            metricsWithoutValue.set(claim.metric, (metricsWithoutValue.get(claim.metric) ?? 0) + 1);
          }
          fireEvent.click(button);
          expect(button.getAttribute("aria-pressed")).toBe("true");
          expect(claimDetail().getAttribute("data-claim-id")).toBe(claim.id);
          const list = screen.queryByRole("list", { name: "Evidence events" });
          const ids = list ? [...list.querySelectorAll("[data-event-id]")].map((el) => el.getAttribute("data-event-id")) : [];
          for (const ev of claim.evidence) expect(ids).toContain(ev.id);
          if (claim.evidence.length === 0) expect(screen.getByText("This claim counts no events in its window.")).toBeTruthy();
        }
        unmount();
      }
    }
    // Reported in the U2 summary: claims drawn in the sentence, claims the sentence states in words, unplaceable.
    console.info(`T2 report: claims=${claims} in-sentence=${inSentence} in-words=${inWords} unplaceable=${unplaceable}`,
      Object.fromEntries(metricsWithoutValue));
    expect(unplaceable).toBe(0);
    expect(inSentence + inWords).toBe(claims);
  });
});

describe("rail", () => {
  it("lists the moments in time order with the selected one marked", () => {
    render(<Harness fx={red} />);
    const options = screen.getAllByRole("option");
    expect(options.map((o) => o.getAttribute("data-moment-id"))).toEqual([...red.moments].sort((a, b) => a.t - b.t).map((m) => m.id));
    expect(options.filter((o) => o.getAttribute("aria-selected") === "true").map((o) => o.getAttribute("data-moment-id"))).toEqual([red.moments[0]!.id]);
  });

  it("moves the selection with the arrow keys, Home and End", () => {
    render(<Harness fx={red} />);
    const first = () => screen.getAllByRole("option")[0]!;
    first().focus();
    fireEvent.keyDown(first(), { key: "ArrowDown" });
    expect(receipt().getAttribute("data-card-id")).toBe(red.moments[1]!.id);
    expect(document.activeElement).toBe(screen.getAllByRole("option")[1]);
    fireEvent.keyDown(document.activeElement!, { key: "End" });
    expect(receipt().getAttribute("data-card-id")).toBe(red.moments.at(-1)!.id);
    fireEvent.keyDown(document.activeElement!, { key: "ArrowUp" });
    expect(receipt().getAttribute("data-card-id")).toBe(red.moments.at(-2)!.id);
    fireEvent.keyDown(document.activeElement!, { key: "Home" });
    expect(receipt().getAttribute("data-card-id")).toBe(red.moments[0]!.id);
  });

  it("only the selected option is a tab stop", () => {
    render(<Harness fx={red} />);
    expect(screen.getAllByRole("option").map((o) => o.getAttribute("tabindex"))).toEqual(["0", ...red.moments.slice(1).map(() => "-1")]);
  });

  it("clamps at both ends and ignores other keys", () => {
    expect(nextIndex("ArrowUp", 0, 3)).toBe(0);
    expect(nextIndex("ArrowRight", 2, 3)).toBe(2);
    expect(nextIndex("a", 1, 3)).toBeNull();
    expect(nextIndex("Home", 2, 0)).toBeNull();
  });
});

const claimOf = (m: Moment, metric: string) => m.claims.find((c) => c.metric === metric);

describe("claim detail", () => {
  const withMetric = (metric: string) => {
    for (const fx of matchFixtures) {
      for (const moment of fx.moments) {
        const c = claimOf(moment, metric);
        if (c && moment.segments.some((s) => s.claim_id === c.id)) return { fx, moment, claim: c };
      }
    }
    throw new Error(`no fixture card with a ${metric} value in its sentence`);
  };
  const open = ({ fx, moment, claim }: ReturnType<typeof withMetric>) => {
    render(<Harness fx={fx} start={moment.id} />);
    fireEvent.click(within(receipt()).getAllByRole("button").find((b) => b.querySelector(`[data-claim-id="${claim.id}"]`))!);
  };

  it("claim_range: the claim's own minutes", () => {
    const hit = withMetric("score");
    open(hit);
    const info = metricsFixture.metrics.find((m) => m.id === "score")!;
    expect(info.window.type).toBe("claim_range");
    const dd = within(claimDetail()).getByText("Window").nextElementSibling!;
    expect(dd.textContent).toBe(hit.claim.start === hit.claim.end ? `at ${hit.claim.end}` : `from ${hit.claim.start} to ${hit.claim.end}`);
    expect(dd.querySelectorAll("[data-claim-id]").length).toBeGreaterThan(0);
  });

  it("rolling: the last N minutes, closing at the claim's end, N from /api/metrics", () => {
    const hit = withMetric("pressure_balance");
    open(hit);
    const info = metricsFixture.metrics.find((m) => m.id === "pressure_balance")!;
    expect(info.window.type).toBe("rolling");
    const dd = within(claimDetail()).getByText("Window").nextElementSibling!;
    expect(dd.textContent).toBe(`the last ${info.window.minutes} minutes played, closing at the claim's end (${hit.claim.end})`);
    expect(dd.querySelector('[data-field="window_minutes"]')!.textContent).toBe(String(info.window.minutes));
  });

  it("possession: the definition sits right beside the value", () => {
    const hit = withMetric("possession");
    open(hit);
    const value = claimDetail().querySelector(`[data-claim-id="${hit.claim.id}"]`)!;
    const def = value.nextElementSibling!;
    expect(def.getAttribute("data-testid")).toBe("definition");
    expect(def.textContent).toBe(metricsFixture.metrics.find((m) => m.id === "possession")!.definition);
    expect(def.textContent).toMatch(/share of pass and dribble events/);
  });

  it("field_tilt: the definition is beside the value as well", () => {
    const hit = withMetric("possession");
    // No fixture card carries a field_tilt claim (it is off the menu): reuse a real claim with that metric.
    const fx = { ...hit.fx, moments: hit.fx.moments.map((m) => m.id === hit.moment.id ? { ...m, claims: m.claims.map((c) => c.id === hit.claim.id ? { ...c, metric: "field_tilt" } : c) } : m) };
    render(<Harness fx={fx} start={hit.moment.id} />);
    fireEvent.click(within(receipt()).getAllByRole("button").find((b) => b.querySelector(`[data-claim-id="${hit.claim.id}"]`))!);
    const def = claimDetail().querySelector(`[data-claim-id="${hit.claim.id}"]`)!.nextElementSibling!;
    expect(def.textContent).toBe(metricsFixture.metrics.find((m) => m.id === "field_tilt")!.definition);
    expect(def.textContent).toMatch(/final-third entries/);
  });

  it("windowKind follows the API window type", () => {
    const c = { start: "10'", end: "20'" };
    const info = (type: "rolling" | "claim_range" | "cumulative") => ({ id: "x", kind: "k", label: "l", definition: "d", window: { type, minutes: null } });
    expect(windowKind(c, info("claim_range")).kind).toBe("range");
    expect(windowKind({ start: "20'", end: "20'" }, info("claim_range")).kind).toBe("at");
    expect(windowKind(c, info("rolling")).kind).toBe("rolling");
    expect(windowKind(c, undefined).kind).toBe("unknown");
  });
});

describe("verification record", () => {
  it("shows the card's recorded checks, labelled as checked by code", () => {
    const moment = red.moments[0]!;
    render(<Harness fx={red} start={moment.id} />);
    const rec = screen.getByRole("region", { name: "Verification record" });
    expect(rec.textContent).toContain("checked by code");
    const nums = [...rec.querySelectorAll("[data-card-id]")].map((el) => [el.getAttribute("data-field"), el.textContent]);
    expect(nums).toEqual([["lint_issues", String(moment.checks.lint_issues)], ["claims_total", String(moment.checks.claims_total)], ["claims_verified", String(moment.checks.claims_verified)]]);
  });
});

describe("evidence", () => {
  const card = red.moments.find((m) => m.type === "red_card")!;
  const sentOff = card.claims.find((c) => c.evidence.some((e) => e.type === "red_card"))!;

  it("an event without a position is listed as 'no location' and not drawn", () => {
    expect(sentOff.evidence.some((e) => e.x === null)).toBe(true);
    render(<Harness fx={red} start={card.id} />);
    fireEvent.click(within(receipt()).getAllByRole("button").find((b) => b.querySelector(`[data-claim-id="${sentOff.id}"]`))!);
    const list = screen.getByRole("list", { name: "Evidence events" });
    expect(within(list).getAllByText("no location").length).toBeGreaterThan(0);
    const located = sentOff.evidence.filter((e) => e.x !== null).length;
    expect(document.querySelectorAll('[data-state="marked"], [data-state="selected"]').length).toBe(located);
  });

  it("selecting an event highlights it in the list and on the pitch", () => {
    const hit = red.moments.flatMap((m) => m.claims.map((c) => ({ m, c }))).find(({ c }) => c.evidence.filter((e) => e.x !== null).length > 1)!;
    render(<Harness fx={red} start={hit.m.id} />);
    fireEvent.click(within(receipt()).getAllByRole("button").find((b) => b.querySelector(`[data-claim-id="${hit.c.id}"]`))!);
    const target = hit.c.evidence.find((e) => e.x !== null)!;
    const row = screen.getByRole("list", { name: "Evidence events" }).querySelector(`[data-event-id="${target.id}"]`)!.closest("button")!;
    fireEvent.click(row);
    expect(row.getAttribute("aria-pressed")).toBe("true");
    expect(document.querySelectorAll('[data-state="selected"]').length).toBe(1);
  });

  it("marks the shape by event type and says the position is the ball's", () => {
    render(<Harness fx={red} start={card.id} />);
    expect(screen.getByText("ball position at each event")).toBeTruthy();
    expect(document.querySelector("[data-shape]")).toBeTruthy();
  });

  it("falls back to the event stream for position and gives the outcome from it", () => {
    const ev = { ...sentOff.evidence[0]!, x: null, y: null };
    const streamed = { ...red.events.find((e) => e.seq === ev.seq)!, x: 10, y: 20, outcome: "scored" };
    const row = joinEvidence(ev, new Map([[ev.seq, streamed]]));
    expect(row.at).toEqual({ x: 10, y: 20 });
    expect(row.outcome).toBe("scored");
    expect(joinEvidence(ev, new Map()).at).toBeNull();
    expect(joinEvidence(ev, new Map()).outcome).toBeNull();
  });

  it("a missing outcome reads 'no outcome', never blank or zero", () => {
    const withoutOutcome = red.moments.flatMap((m) => m.claims.map((c) => ({ m, c }))).find(({ c }) => c.evidence.some((e) => red.events.find((x) => x.seq === e.seq)?.outcome === null))!;
    render(<Harness fx={red} start={withoutOutcome.m.id} />);
    fireEvent.click(within(receipt()).getAllByRole("button").find((b) => b.querySelector(`[data-claim-id="${withoutOutcome.c.id}"]`))!);
    expect(screen.getAllByText("no outcome").length).toBeGreaterThan(0);
  });
});

describe("states", () => {
  it("no moments: a true empty statement, no empty boxes", () => {
    render(<Harness fx={{ ...red, moments: [] }} />);
    expect(screen.getByText("No narrated moments in this match.")).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Receipt" })).toBeNull();
  });

  it("metrics loading: a skeleton line in place of the definition", () => {
    render(<Harness fx={red} metrics={{ status: "loading", retry: () => {} }} />);
    expect(within(claimDetail()).getByRole("status").textContent).toContain("Loading the definition");
  });

  it("metrics failed: an alert with Retry that calls retry", () => {
    const retry = vi.fn();
    render(<Harness fx={red} metrics={{ status: "error", error: new Error("boom"), retry }} />);
    expect(within(claimDetail()).getByRole("alert").textContent).toContain("Could not load the metric definitions.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("a metric the registry does not know has no definition rather than an invented one", () => {
    const fx = { ...red };
    render(<Harness fx={fx} metrics={{ status: "ok", data: { ...metricsFixture, metrics: [] }, retry: () => {} }} />);
    expect(claimDetail().textContent).toContain("No definition is published for this metric.");
  });
});

describe("wording", () => {
  const sources = import.meta.glob<string>(["/src/**/*.{ts,tsx}", "!/src/**/*.test.*"], { query: "?raw", import: "default", eager: true });
  it("never says an agent verified anything (no Verifier agent exists yet)", () => {
    expect(Object.keys(sources).length).toBeGreaterThan(10);
    const hits = Object.entries(sources).filter(([, text]) => /agent[- ]verif|verified by (an )?agent|verifier agent/i.test(text));
    expect(hits.map(([p]) => p)).toEqual([]);
  });
});

describe("evidence rows", () => {
  it("lists a shared event once", () => {
    const ev = red.moments[0]!.claims.flatMap((c) => c.evidence)[0]!;
    expect(rowsOf([ev, ev], new Map()).length).toBe(1);
  });
});
