import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Moment, Source } from "../types";
import { MomentCard } from "./MomentCard";
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
          },
        ],
      },
    ],
    trace: [],
  };
}

describe("MomentCard", () => {
  it.each([
    ["llm", "LLM · verified"],
    ["template", "Template"],
    ["template_fallback", "Template fallback"],
  ] as const)("labels the %s source", (source, label) => {
    const { container } = render(
      <MomentCard moment={moment(source)} teams={teams} selected={false} fresh={false} onSelect={() => {}} onTrace={() => {}} />,
    );
    const badge = container.querySelector("[data-source]")!;
    expect(badge.getAttribute("data-source")).toBe(source);
    expect(badge.className).toContain(`source-${source}`);
    expect(badge.textContent).toContain(label);
  });

  it("shows minute, type, text and the claim → evidence list", () => {
    const onSelect = vi.fn();
    const onTrace = vi.fn();
    render(
      <MomentCard moment={moment("llm")} teams={teams} selected={false} fresh={false} onSelect={onSelect} onTrace={onTrace} />,
    );
    expect(screen.getByText("Goal")).toBeTruthy();
    expect(screen.getByText(/Murek Brestani scored at 22'/)).toBeTruthy();
    expect(screen.getByText("Verified claims (1)")).toBeTruthy();
    const evidence = screen.getByRole("list", { name: "Evidence for goals" });
    expect(within(evidence).getByText("Counted events")).toBeTruthy();
    expect(within(evidence).getByText(/goal · Murek Brestani/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Trace" }));
    expect(onTrace).toHaveBeenCalledWith("m-42-red_card_swing-M002");
    expect(onSelect).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText(/Murek Brestani scored at 22'/));
    expect(onSelect).toHaveBeenCalledWith("m-42-red_card_swing-M002");
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
