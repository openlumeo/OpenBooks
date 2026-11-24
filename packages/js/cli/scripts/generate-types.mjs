import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const here = dirname(fileURLToPath(import.meta.url));
const read = (n) => JSON.parse(readFileSync(join(here, "../schema", n), "utf8"));
const opts = { bannerComment: "", additionalProperties: true, strictIndexSignatures: false, format: true };
const out =
  "// GENERATED from schema/*.json by scripts/generate-types.mjs. Do not edit; run `pnpm generate`.\n\n" +
  (await compile(read("openbooks.v1.schema.json"), "OpenBooksDocument", opts)) + "\n" +
  (await compile(read("openbooks.v1.refusal.schema.json"), "OpenBooksRefusal", opts));
const target = join(here, "../src/core/generated/openbooks.ts");
if (process.argv.includes("--check")) {
  let cur = "";
  try { cur = readFileSync(target, "utf8"); } catch {}
  if (cur.replace(/\r\n/g, "\n") !== out) { console.error("src/generated/openbooks.ts is stale: run `pnpm generate`"); process.exit(1); }
} else {
  mkdirSync(dirname(target), { recursive: true });
  writeFileSync(target, out, "utf8");
  console.log("wrote src/generated/openbooks.ts");
}
