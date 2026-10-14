import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Series } from "../api/types";
import { typeLabel } from "../design/TypeGlyph";
import { matchFixtures, metricsFixture, type MatchFixture } from "../test/fixtures";
import { AppRoutes } from "./App";
import { shortcutFor } from "./keys";
import { openAt } from "./MatchView";
import { bandPaths } from "./PressureBand";
import { SEEK, timeAtX } from "./Timeline";
import { FLIP_MS } from "./useFlip";

const red = matchFixtures.find((m) => m.summary.id === "red_card_swing_seed42")!;

/** fetch answered from the real fixtures; `override` replaces one match's data (e.g. no moments). */
function serve(opts: { fail?: RegExp; pending?: RegExp; override?: Partial<MatchFixture> } = {}) {
  const byId = new Map(matchFixtures.map((m) => [m.summary.id, { ...m, ...(m === red ? opts.override : {}) }]));
  const json = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status }));
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (opts.pending?.test(url)) return new Promise<Response>(() => {});
    if (opts.fail?.test(url)) return json({ detail: "boom" }, 500);
    if (url === "/api/metrics") return json(metricsFixture);
    if (url === "/api/matches") return json(matchFixtures.map((m) => m.summary));
    const m = url.match(/^\/api\/matches\/([^/?]+)(?:\/(\w+))?/);
    const f = m && byId.get(decodeURIComponent(m[1]!));
    if (!f) return json({ detail: "not found" }, 404);
    const part = m![2];
    if (!part) return json(f.detail);
    if (part === "moments") return json(f.moments);
    if (part === "events") return json(f.events);
    if (part === "series") return json(f.series);
    return json({ detail: "not found" }, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function stubMedia(wide = true, reduced = false) {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: q === "(min-width: 768px)" ? wide : q === "(prefers-reduced-motion: reduce)" ? reduced : false,
    addEventListener() {},
    removeEventListener() {},
  }));
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  );
}

beforeEach(() => stubMedia());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const narration = () => screen.getByRole("region", { name: "Narration" });
const cardText = () => narration().querySelector("[data-card-id]")?.textContent;

describe("routes and states", () => {
  it("/ shows the first match from the API, paused on its first model card", async () => {
    serve();
    renderAt("/");
    const first = matchFixtures[0]!;
    const llm = first.moments.find((m) => m.source === "llm")!;
    await waitFor(() => expect(narration()).toBeTruthy());
    expect(cardText()).toBe(llm.text);
    expect(screen.getByRole("button", { name: "Play" })).toBeTruthy();
    expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe(first.summary.id);
  });

  it("deep link: ?moment opens that card", async () => {
    serve();
    const card = red.moments.find((m) => m.type === "red_card")!;
    renderAt(`/match/${red.summary.id}?moment=${card.id}`);
    await waitFor(() => expect(cardText()).toBe(card.text));
    expect(screen.getByRole("slider", { name: "Match time" }).getAttribute("aria-valuenow")).toBe(String(card.t));
  });

  it("unknown match id: says so", async () => {
    serve();
    renderAt("/match/nope");
    await waitFor(() => expect(screen.getByText('No match with the id "nope" in the publication store.')).toBeTruthy());
  });

  it("unknown page: says so", async () => {
    serve();
    renderAt("/no/such/page");
    expect(await screen.findByText("There is no page at this address.")).toBeTruthy();
  });

  it("loading: a skeleton with a status", () => {
    serve({ pending: /\/events$/ });
    renderAt(`/match/${red.summary.id}`);
    expect(screen.getByRole("status").getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText("Loading the match…")).toBeTruthy();
  });

  it("error: shows the failure and retries", async () => {
    const fetchMock = serve({ fail: /\/series/ });
    renderAt(`/match/${red.summary.id}`);
    const retry = await screen.findByRole("button", { name: "Retry" });
    expect(screen.getByRole("alert").textContent).toContain("Could not load the match.");
    serve();
    fireEvent.click(retry);
    await waitFor(() => expect(narration()).toBeTruthy());
    expect(fetchMock).toHaveBeenCalled();
  });

  it("empty: a match without narrated moments says so, the stage still plays", async () => {
    serve({ override: { moments: [] } });
    renderAt(`/match/${red.summary.id}`);
    expect(await screen.findByText("No narrated moments in this match.")).toBeTruthy();
    expect(screen.getByRole("group", { name: "Score" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Next moment" })).toHaveProperty("disabled", true);
  });

  it("?mode=proof opens the Proof face on the deep-linked moment", async () => {
    serve();
    const card = red.moments.find((m) => m.type === "red_card")!;
    renderAt(`/match/${red.summary.id}?mode=proof&moment=${card.id}`);
    const receipt = await screen.findByRole("region", { name: "Receipt" });
    expect(receipt.getAttribute("data-card-id")).toBe(card.id);
    expect(screen.getByRole("tab", { name: "Proof" }).getAttribute("aria-selected")).toBe("true");
  });

  it("the top bar has no left menu, a SYNTHETIC DATA label and a theme switch", async () => {
    serve();
    renderAt(`/match/${red.summary.id}`);
    await waitFor(() => expect(narration()).toBeTruthy());
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(screen.getAllByText("SYNTHETIC DATA").length).toBe(2); // top bar + stage
    const theme = screen.getByRole("button", { name: /^Switch to (dark|light) theme$/ });
    const before = document.documentElement.dataset.theme;
    fireEvent.click(theme);
    expect(document.documentElement.dataset.theme).not.toBe(before);
    delete document.documentElement.dataset.theme;
  });
});

describe("transport and keyboard", () => {
  async function ready() {
    serve();
    renderAt(`/match/${red.summary.id}?moment=${red.moments[2]!.id}`);
    await waitFor(() => expect(cardText()).toBe(red.moments[2]!.text));
  }

  it("Space plays and pauses; arrows step moments; G toggles guides; ? opens help", async () => {
    await ready();
    fireEvent.keyDown(document.body, { key: " " });
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy();
    fireEvent.keyDown(document.body, { key: " " });
    expect(screen.getByRole("button", { name: "Play" })).toBeTruthy();
    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    expect(cardText()).toBe(red.moments[3]!.text);
    fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    fireEvent.keyDown(document.body, { key: "ArrowLeft" });
    expect(cardText()).toBe(red.moments[1]!.text);
    expect(screen.queryByTestId("guides")).toBeNull();
    fireEvent.keyDown(document.body, { key: "g" });
    expect(screen.getByTestId("guides")).toBeTruthy();
    fireEvent.keyDown(document.body, { key: "?" });
    expect(screen.getByRole("dialog", { name: "Keyboard shortcuts" })).toBeTruthy();
  });

  it("the timeline seeks by keyboard; a moment glyph shows its card", async () => {
    await ready();
    const slider = screen.getByRole("slider", { name: "Match time" });
    const t0 = Number(slider.getAttribute("aria-valuenow"));
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(Number(slider.getAttribute("aria-valuenow"))).toBe(t0 + SEEK.step);
    fireEvent.keyDown(slider, { key: "Home" });
    expect(slider.getAttribute("aria-valuenow")).toBe("0");
    expect(screen.queryByRole("region", { name: "Narration" })).toBeNull(); // seek clears the lower third
    const target = red.moments[5]!;
    fireEvent.click(screen.getByRole("button", { name: `${typeLabel(target.type)}, ${target.minute_label}` }));
    expect(cardText()).toBe(target.text);
    expect(slider.getAttribute("aria-valuetext")).toBe(target.minute_label);
  });

  it("speed choice states its wall time from the match duration", async () => {
    await ready();
    fireEvent.click(screen.getByRole("radio", { name: "Faster" }));
    expect(screen.getByText(`whole match in about ${Math.round(red.detail.duration_t / 300)} s`)).toBeTruthy();
  });

  it("plays in time with the wall clock", async () => {
    await ready();
    vi.useFakeTimers();
    const slider = screen.getByRole("slider", { name: "Match time" });
    const t0 = Number(slider.getAttribute("aria-valuenow"));
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    act(() => vi.advanceTimersByTime(1000));
    expect(Number(slider.getAttribute("aria-valuenow"))).toBe(t0 + 60);
  });
});

describe("pure helpers", () => {
  it("shortcuts stay out of fields, buttons keep Space, sliders/tabs/radios keep arrows", () => {
    const make = (html: string) => {
      const d = document.createElement("div");
      d.innerHTML = html;
      document.body.append(d);
      return d.firstElementChild!;
    };
    expect(shortcutFor(" ", document.body)).toBe("toggle");
    expect(shortcutFor(" ", make("<button>x</button>"))).toBeNull();
    expect(shortcutFor("ArrowRight", make("<button>x</button>"))).toBe("next");
    expect(shortcutFor("g", make("<input />"))).toBeNull();
    expect(shortcutFor("?", make("<textarea></textarea>"))).toBeNull();
    expect(shortcutFor("ArrowLeft", make('<div role="slider"></div>'))).toBeNull();
    expect(shortcutFor("ArrowLeft", make('<button role="radio">x</button>'))).toBeNull();
    expect(shortcutFor("g", document.body, { meta: true })).toBeNull();
    expect(shortcutFor("x", document.body)).toBeNull();
  });

  it("deep-link parameters: valid moment, then valid t, else the first llm card", () => {
    const m = red.moments;
    const d = red.detail.duration_t;
    expect(openAt(new URLSearchParams(`moment=${m[1]!.id}`), m, d)).toEqual({ showId: m[1]!.id, t: 0 });
    expect(openAt(new URLSearchParams("moment=nope&t=600"), m, d)).toEqual({ showId: null, t: 600 });
    expect(openAt(new URLSearchParams("t=-4"), m, d).showId).toBe(m.find((x) => x.source === "llm")!.id);
    expect(openAt(new URLSearchParams("t=99999999"), m, d).t).toBe(d);
    expect(openAt(new URLSearchParams(""), [], d)).toEqual({ showId: null, t: 0 });
  });

  it("timeAtX maps a pointer to the match clock, clamped", () => {
    expect(timeAtX(150, { left: 100, width: 200 }, 1000)).toBe(250);
    expect(timeAtX(0, { left: 100, width: 200 }, 1000)).toBe(0);
    expect(timeAtX(999, { left: 100, width: 200 }, 1000)).toBe(1000);
  });

  it("the pressure band breaks at null points and is never drawn as zero", () => {
    const s = red.series;
    const runs = s.points.reduce<number[][]>((acc, p, i) => {
      if (p.value === null) return acc;
      const last = acc[acc.length - 1];
      if (last && s.points[i - 1]?.value !== null && i > 0) last.push(i);
      else acc.push([i]);
      return acc;
    }, []);
    expect(bandPaths(s, red.detail.duration_t).length).toBe(runs.filter((r) => r.length > 1).length);
    const allNull: Series = { ...s, points: s.points.map((p) => ({ ...p, value: null })) };
    expect(bandPaths(allNull, red.detail.duration_t)).toEqual([]);
  });

  it("the band's accessible name comes from the API label and definition", async () => {
    serve();
    renderAt(`/match/${red.summary.id}`);
    const band = await screen.findByRole("img", { name: new RegExp(red.series.label) });
    expect(band.getAttribute("aria-label")).toContain(red.series.definition);
  });
});


describe("Flip between On Air and Proof", () => {
  const card = red.moments.find((m) => m.type === "red_card")!;
  const other = red.moments.find((m) => m.id !== card.id && m.t < card.t)!;
  const receipt = () => screen.queryByRole("region", { name: "Receipt" });
  const press = (key: string) => fireEvent.keyDown(document.body, { key });
  const settle = () => act(() => void vi.advanceTimersByTime(FLIP_MS.out + FLIP_MS.in + 20));

  async function open(reduced: boolean, path = `/match/${red.summary.id}?moment=${card.id}`) {
    stubMedia(true, reduced);
    serve();
    renderAt(path);
    await waitFor(() => expect(screen.queryByRole("tabpanel")).toBeTruthy());
    if (!reduced) vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] }); // after loading: only the flip timers
  }

  it("the whole turn is within the 400 ms cap", () => {
    expect(FLIP_MS.out + FLIP_MS.in).toBeLessThanOrEqual(400);
  });

  it("the seal is a visible button labelled Proof · P that opens the shown card in Proof", async () => {
    await open(false);
    const button = screen.getByRole("button", { name: /Proof · P/ });
    expect(button.textContent).toContain("Proof · P");
    expect(button.textContent).toContain("Checked by code");
    fireEvent.click(button);
    expect(document.querySelector('[data-face="air"]')).toBeTruthy(); // still turning
    settle();
    expect(receipt()!.getAttribute("data-card-id")).toBe(card.id);
    expect(screen.getByRole("tab", { name: "Proof" }).getAttribute("aria-selected")).toBe("true");
  });

  it("the face swaps halfway through the turn, not at once", async () => {
    await open(false);
    press("p");
    expect(receipt()).toBeNull();
    act(() => void vi.advanceTimersByTime(FLIP_MS.out + 5));
    expect(receipt()).toBeTruthy();
  });

  it("reduced motion: P flips at once, no timers", async () => {
    await open(true);
    press("P");
    expect(receipt()!.getAttribute("data-card-id")).toBe(card.id);
    press("P");
    expect(receipt()).toBeNull();
    expect(cardText()).toBe(card.text);
  });

  it("P in Proof returns to On Air at that moment's time, paused, with its card", async () => {
    await open(true, `/match/${red.summary.id}?mode=proof&moment=${card.id}`);
    fireEvent.click(document.querySelector(`[data-moment-id="${other.id}"]`)!);
    press("p");
    expect(cardText()).toBe(other.text);
    expect(screen.getByRole("button", { name: "Play" })).toBeTruthy();
    expect(screen.getByRole("slider", { name: "Match time" }).getAttribute("aria-valuenow")).toBe(String(other.t));
  });

  it("with no card on air, Proof opens the latest moment before the playhead", async () => {
    await open(true, `/match/${red.summary.id}?t=${card.t + 5}`);
    press("p");
    expect(receipt()!.getAttribute("data-card-id")).toBe(card.id);
  });

  it("entering Proof pauses playback", async () => {
    await open(true);
    fireEvent.click(screen.getByRole("button", { name: "Play" }));
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy();
    press("p");
    press("p");
    expect(screen.getByRole("button", { name: "Play" })).toBeTruthy();
  });

  it("the Proof tab flips with the same carry-over", async () => {
    await open(true);
    fireEvent.mouseDown(screen.getByRole("tab", { name: "Proof" }));
    expect(receipt()!.getAttribute("data-card-id")).toBe(card.id);
  });

  it("in Proof the arrow keys leave On Air's cards alone and P in a field does nothing", async () => {
    await open(true, `/match/${red.summary.id}?mode=proof&moment=${card.id}`);
    fireEvent.keyDown(document.body, { key: "ArrowRight" });
    expect(receipt()!.getAttribute("data-card-id")).toBe(card.id);
    const select = screen.getByRole("combobox");
    fireEvent.keyDown(select, { key: "p" });
    expect(receipt()).toBeTruthy();
  });

  it("the shortcut list names P", () => {
    expect(shortcutFor("p", document.body)).toBe("flip");
    expect(shortcutFor("P", document.createElement("input"))).toBeNull();
    expect(shortcutFor("p", document.body, { ctrl: true })).toBeNull();
  });
});
