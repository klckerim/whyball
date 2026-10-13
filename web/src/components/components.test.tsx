import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Moment, Source } from "../types";
import { EvidencePanel } from "./EvidencePanel";
import { MomentCard } from "./MomentCard";
import { SidePanel } from "./SidePanel";
import { TracePanel } from "./TracePanel";

afterEach(cleanup);

const teams = { home: "Brannoch FC", away: "Morvane Athletic" };

function moment(source: Source): Moment {
  return {
    id: "m-42-red_card_swing-M002",
    t: 1320,
    period: 1,
    minute: 22,
    second: 0,
    minute_label: "22'",
    at_seq: 127,
    type: "goal",
    team: "home",
    importance: 1,
    text: "Murek Brestani scored at 22', and the score is Brannoch FC 1–0 Morvane Athletic.",
    source,
    prompt_version: source === "llm" ? "foundry-v5.2:gpt-5-mini" : "template-v1",
    run_id: null,
    claims: [
      {
        id: "goal",
        kind: "count",
        metric: "goals",
        label: "goals",
        team: "home",
        player: "Murek Brestani",
        comparison: "eq",
        value: 1,
        display: "1",
        start: "22'",
        end: "22'",
        evidence: [
          {
            id: "m-42-red_card_swing#127",
            seq: 127,
            type: "goal",
            team: "home",
            player: "Murek Brestani",
            period: 1,
            minute: 22,
            second: 0,
            minute_label: "22'",
            x: 96.5,
            y: 30.1,
          },
        ],
      },
    ],
    trace: [],
  };
}

describe("MomentCard", () => {
  const card = (source: Source, over: Partial<Parameters<typeof MomentCard>[0]> = {}) =>
    render(
      <MomentCard
        moment={moment(source)}
        teams={teams}
        selected={false}
        activeClaim={null}
        fresh={false}
        onSelect={() => {}}
        onSelectClaim={() => {}}
        onPreviewClaim={() => {}}
        {...over}
      />,
    );

  it.each([
    ["llm", "LLM · verified"],
    ["template", "Template"],
    ["template_fallback", "Template fallback"],
  ] as const)("labels the %s source", (source, label) => {
    const { container } = card(source);
    const badge = container.querySelector("[data-source]")!;
    expect(badge.getAttribute("data-source")).toBe(source);
    expect(badge.className).toContain(`source-${source}`);
    expect(badge.textContent).toContain(label);
  });

  it("shows minute, type, the verified strip and no Trace link", () => {
    card("llm");
    expect(screen.getByText("Goal")).toBeTruthy();
    expect(screen.getByText("Verified claims (1)")).toBeTruthy();
    expect(screen.getByText("1 check passed")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Trace" })).toBeNull();
  });

  it("marks code-rendered values; clicking one selects its claim, hovering previews it", () => {
    const onSelect = vi.fn();
    const onSelectClaim = vi.fn();
    const onPreviewClaim = vi.fn();
    const { container } = card("llm", { onSelect, onSelectClaim, onPreviewClaim });
    const vals = [...container.querySelectorAll(".text .val")].map((v) => v.textContent);
    expect(vals).toEqual(["Murek Brestani", "22'"]);
    const name = screen.getByRole("button", { name: "Murek Brestani" });
    fireEvent.mouseEnter(name);
    expect(onPreviewClaim).toHaveBeenLastCalledWith("m-42-red_card_swing-M002", "goal");
    fireEvent.click(name);
    expect(onSelectClaim).toHaveBeenCalledWith("m-42-red_card_swing-M002", "goal");
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText(/and the score is/));
    expect(onSelect).toHaveBeenCalledWith("m-42-red_card_swing-M002");
  });

  it("keeps the model and run small, with the full form in the tooltip", () => {
    const m = { ...moment("llm"), run_id: "foundry-v5.2:gpt-5-mini@2026-10-13T15:02:48+00:00" };
    const { container } = render(
      <MomentCard moment={m} teams={teams} selected={false} activeClaim={null} fresh={false} onSelect={() => {}} onSelectClaim={() => {}} onPreviewClaim={() => {}} />,
    );
    const meta = container.querySelector(".run-meta")!;
    expect(meta.textContent).toBe("gpt-5-mini · run 2026-10-13");
    expect(meta.getAttribute("title")).toContain("foundry-v5.2:gpt-5-mini@2026-10-13T15:02:48+00:00");
  });
});

describe("EvidencePanel", () => {
  it("lists the claim's events with type, player and minute, and selects one", () => {
    const m = moment("llm");
    const onSelectEvent = vi.fn();
    const { container } = render(
      <EvidencePanel moment={m} claim={m.claims[0]} eventId={null} teams={teams} onSelectClaim={() => {}} onSelectEvent={onSelectEvent} />,
    );
    const list = screen.getByRole("list", { name: "Events for goals" });
    expect(within(list).getByText("22'")).toBeTruthy();
    expect(within(list).getByText("goal")).toBeTruthy();
    expect(within(list).getByText("Murek Brestani")).toBeTruthy();
    expect(container.querySelectorAll(".pitch .dot")).toHaveLength(1);
    fireEvent.click(within(list).getByRole("button"));
    expect(onSelectEvent).toHaveBeenCalledWith("m-42-red_card_swing#127");
  });

  it("rings the selected event on the pitch and flags events without a location", () => {
    const m = moment("llm");
    const ev = { ...m.claims[0].evidence[0], id: "e2", type: "red_card", x: null, y: null };
    const claim = { ...m.claims[0], evidence: [m.claims[0].evidence[0], ev] };
    const { container } = render(
      <EvidencePanel moment={m} claim={claim} eventId="m-42-red_card_swing#127" teams={teams} onSelectClaim={() => {}} onSelectEvent={() => {}} />,
    );
    expect(container.querySelector(".pitch .dot.selected")).toBeTruthy();
    expect(container.querySelector(".pitch .ring")).toBeTruthy();
    expect(screen.getByText("no location")).toBeTruthy();
  });
});

describe("SidePanel", () => {
  it("opens on Evidence and moves between tabs with the arrow keys", () => {
    const onTab = vi.fn();
    render(<SidePanel tab="evidence" onTab={onTab} open={false} onOpen={() => {}} peek="peek" evidence={<p>EV</p>} trace={<p>TR</p>} />);
    const evidence = screen.getByRole("tab", { name: "Evidence" });
    expect(evidence.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("EV")).toBeTruthy();
    fireEvent.keyDown(evidence, { key: "ArrowRight" });
    expect(onTab).toHaveBeenCalledWith("trace");
  });
});

describe("TracePanel", () => {
  it("shows the empty state without a trace", () => {
    render(<TracePanel moment={moment("llm")} />);
    expect(screen.getByText("No trace yet")).toBeTruthy();
  });

  it("asks for a card when nothing is selected", () => {
    render(<TracePanel moment={null} />);
    expect(screen.getByText(/Select a card/)).toBeTruthy();
  });

  it("lists trace steps when present", () => {
    const m = { ...moment("llm"), trace: [{ attempt: 1, step: "verify" as const, ok: false, codes: ["value_mismatch"] }] };
    render(<TracePanel moment={m} />);
    expect(screen.getByText("verify")).toBeTruthy();
    expect(screen.getByText(/value_mismatch/)).toBeTruthy();
  });
});
