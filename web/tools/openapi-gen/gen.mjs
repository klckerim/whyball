// Generates web/src/api/schema.gen.ts from web/openapi.json (written by `python -m app.api.openapi`).
//   node tools/openapi-gen/gen.mjs           write the file   (npm run gen:api)
//   node tools/openapi-gen/gen.mjs --check   exit 1 on drift  (npm run check:api, CI)
// Needs `npm ci --prefix tools/openapi-gen` first (isolated install, docs/DESIGN.md D10).
import { readFile, writeFile } from "node:fs/promises";

const SCHEMA = new URL("../../openapi.json", import.meta.url);
const OUT = new URL("../../src/api/schema.gen.ts", import.meta.url);
const HEADER =
  "// Generated from web/openapi.json by web/tools/openapi-gen (openapi-typescript). Do not edit:\n" +
  "// run `.venv/bin/python -m app.api.openapi` then `cd web && npm run gen:api`.\n\n";

let openapiTS, astToString;
try {
  ({ default: openapiTS, astToString } = await import("openapi-typescript"));
} catch {
  console.error("openapi-typescript is not installed: run `npm ci --prefix tools/openapi-gen` in web/");
  process.exit(2);
}

const text = HEADER + astToString(await openapiTS(JSON.parse(await readFile(SCHEMA, "utf8"))));

if (process.argv.includes("--check")) {
  const current = await readFile(OUT, "utf8").catch(() => "");
  if (current !== text) {
    console.error("src/api/schema.gen.ts is stale: run `npm run gen:api`");
    process.exit(1);
  }
} else {
  await writeFile(OUT, text);
  console.log("wrote src/api/schema.gen.ts");
}
