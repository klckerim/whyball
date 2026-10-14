// Keyboard shortcuts (UI_SPEC §10): which key a target may receive. Typing in a field never triggers
// one; Space keeps its own meaning on buttons and links; arrows keep theirs on sliders, tabs and radios.
export type Shortcut = "toggle" | "prev" | "next" | "guides" | "help" | "flip";

const TEXT_FIELD = 'input, textarea, select, [contenteditable=""], [contenteditable="true"]';
const OWNS_SPACE = `${TEXT_FIELD}, button, a[href], [role="button"], [role="slider"], [role="tab"], [role="radio"], [role="checkbox"]`;
const OWNS_ARROWS = `${TEXT_FIELD}, [role="slider"], [role="tab"], [role="radio"], [role="menuitem"], [role="option"]`;

export function shortcutFor(key: string, target: EventTarget | null, mods: { ctrl?: boolean; meta?: boolean; alt?: boolean } = {}): Shortcut | null {
  if (mods.ctrl || mods.meta || mods.alt) return null;
  const el = target instanceof Element ? target : null;
  const inside = (sel: string) => !!el?.closest(sel);
  switch (key) {
    case " ":
      return inside(OWNS_SPACE) ? null : "toggle";
    case "ArrowLeft":
      return inside(OWNS_ARROWS) ? null : "prev";
    case "ArrowRight":
      return inside(OWNS_ARROWS) ? null : "next";
    case "p":
    case "P":
      return inside(TEXT_FIELD) ? null : "flip";
    case "g":
    case "G":
      return inside(TEXT_FIELD) ? null : "guides";
    case "?":
      return inside(TEXT_FIELD) ? null : "help";
    default:
      return null;
  }
}

export const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "Space", action: "Play or pause" },
  { keys: "← / →", action: "Previous or next moment" },
  { keys: "P", action: "Flip between On Air and Proof" },
  { keys: "G", action: "Show or hide the safe-area guides" },
  { keys: "?", action: "This help" },
];
