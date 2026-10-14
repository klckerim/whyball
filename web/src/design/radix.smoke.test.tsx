// Smoke test: the five Radix primitives UI v2 uses render and keep their keyboard/ARIA behaviour under
// our React version (docs/DESIGN.md D13). No styling or app code involved.
import * as Dialog from "@radix-ui/react-dialog";
import * as Popover from "@radix-ui/react-popover";
import * as Tabs from "@radix-ui/react-tabs";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import * as Tooltip from "@radix-ui/react-tooltip";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

beforeAll(() => {
  // jsdom has no ResizeObserver; Radix's popper (Tooltip, Popover) measures with it.
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(cleanup);

describe("Radix primitives", () => {
  it("Tabs: roles, and arrow keys move the selection", async () => {
    render(
      <Tabs.Root defaultValue="air">
        <Tabs.List aria-label="Mode">
          <Tabs.Trigger value="air">On Air</Tabs.Trigger>
          <Tabs.Trigger value="proof">Proof</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content value="air">stage</Tabs.Content>
        <Tabs.Content value="proof">receipt</Tabs.Content>
      </Tabs.Root>,
    );
    const [air, proof] = screen.getAllByRole("tab");
    expect(screen.getByRole("tablist", { name: "Mode" })).toBeTruthy();
    expect(air!.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").textContent).toBe("stage");
    act(() => air!.focus());
    fireEvent.keyDown(air!, { key: "ArrowRight" });
    await waitFor(() => expect(document.activeElement).toBe(proof)); // roving focus moves on a timeout
    expect(proof!.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tabpanel").textContent).toBe("receipt");
  });

  it("Dialog: opens with focus inside, Escape closes it", () => {
    render(
      <Dialog.Root>
        <Dialog.Trigger>Open receipt</Dialog.Trigger>
        <Dialog.Portal>
          <Dialog.Content>
            <Dialog.Title>Receipt</Dialog.Title>
            <Dialog.Description>Claims and evidence</Dialog.Description>
            <Dialog.Close>Close</Dialog.Close>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>,
    );
    fireEvent.click(screen.getByText("Open receipt"));
    const dialog = screen.getByRole("dialog", { name: "Receipt" });
    expect(dialog.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(document.activeElement!, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("ToggleGroup: single choice with aria state", () => {
    render(
      <ToggleGroup.Root type="single" defaultValue="fan" aria-label="Experience">
        <ToggleGroup.Item value="fan">Fan</ToggleGroup.Item>
        <ToggleGroup.Item value="analyst">Analyst</ToggleGroup.Item>
      </ToggleGroup.Root>,
    );
    const fan = screen.getByText("Fan");
    const analyst = screen.getByText("Analyst");
    expect(fan.getAttribute("aria-checked") ?? fan.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(analyst);
    expect(analyst.getAttribute("data-state")).toBe("on");
    expect(fan.getAttribute("data-state")).toBe("off");
  });

  it("Popover: trigger opens the content", () => {
    render(
      <Popover.Root>
        <Popover.Trigger>Definition</Popover.Trigger>
        <Popover.Portal>
          <Popover.Content>pressure balance</Popover.Content>
        </Popover.Portal>
      </Popover.Root>,
    );
    const trigger = screen.getByText("Definition");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("dialog").textContent).toBe("pressure balance");
  });

  it("Tooltip: open content is announced as a tooltip", () => {
    render(
      <Tooltip.Provider>
        <Tooltip.Root open>
          <Tooltip.Trigger>Seal</Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content>verified</Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      </Tooltip.Provider>,
    );
    expect(screen.getByRole("tooltip").textContent).toBe("verified");
  });
});
