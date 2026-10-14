// UI review screenshots against the real build and the real publication store.
//   cd web && npm run build && npm ci --prefix tools/shots && node tools/shots/shots.mjs [out-dir]
// Starts uvicorn on a free port (serving web/dist), opens the red card moment of red_card_swing_seed42,
// and writes three PNGs (default out-dir: notes/shots/u1, not tracked). Uses the installed Google Chrome.
import { spawn } from "node:child_process";
import { mkdir } from "node:fs/promises";
import { createServer } from "node:net";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const OUT = resolve(ROOT, process.argv[2] ?? "notes/shots/u1");
const MATCH = "red_card_swing_seed42";
const SHOTS = [
  { name: "1440x900-dark", width: 1440, height: 900, colorScheme: "dark" },
  { name: "1920x1080-light", width: 1920, height: 1080, colorScheme: "light" },
  { name: "390x844-dark", width: 390, height: 844, colorScheme: "dark" },
];

const port = await new Promise((ok) => {
  const s = createServer().listen(0, "127.0.0.1", () => {
    const { port } = s.address();
    s.close(() => ok(port));
  });
});
const base = `http://127.0.0.1:${port}`;
const server = spawn(resolve(ROOT, ".venv/bin/uvicorn"), ["app.api.main:app", "--host", "127.0.0.1", "--port", String(port)], {
  cwd: ROOT,
  stdio: "ignore",
});

try {
  for (let i = 0; ; i++) {
    try {
      if ((await fetch(`${base}/healthz`)).ok) break;
    } catch {}
    if (i > 100) throw new Error("uvicorn did not start");
    await new Promise((r) => setTimeout(r, 100));
  }
  const moments = await (await fetch(`${base}/api/matches/${MATCH}/moments`)).json();
  const card = moments.find((m) => m.type === "red_card");
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch({ channel: "chrome" });
  for (const s of SHOTS) {
    const page = await browser.newPage({ viewport: { width: s.width, height: s.height }, colorScheme: s.colorScheme });
    const errors = [];
    page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(`${base}/match/${MATCH}?moment=${encodeURIComponent(card.id)}`);
    await page.getByRole("region", { name: "Narration" }).waitFor();
    await page.evaluate(() => document.fonts.ready);
    await page.evaluate(() => Promise.all(document.getAnimations().map((a) => a.finished))); // lower-third fade-in
    const scroll = await page.evaluate(() => ({ x: document.documentElement.scrollWidth > window.innerWidth, h: document.documentElement.scrollHeight }));
    const path = resolve(OUT, `${s.name}.png`);
    await page.screenshot({ path });
    console.log(`${path}  horizontal-scroll=${scroll.x}  page-height=${scroll.h}  console-errors=${errors.length}`);
    for (const e of errors) console.log(`  ${e}`);
    await page.close();
  }
  await browser.close();
} finally {
  server.kill();
}
