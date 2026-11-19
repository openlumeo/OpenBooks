// The Python package owns the schema. This copies it next to the JS package (so it ships in the npm tarball and the types
// and validation are built from the same file). `--check` fails instead of writing, for CI.
import { copyFileSync, mkdirSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const from = join(here, "../../../py/openbooks/src/openbooks/core/schema");
const to = join(here, "../schema");
const check = process.argv.includes("--check");
mkdirSync(to, { recursive: true });
let drift = 0;
for (const name of readdirSync(from).filter((n) => n.endsWith(".json"))) {
  const a = readFileSync(join(from, name), "utf8").replace(/\r\n/g, "\n");
  let b = "";
  try { b = readFileSync(join(to, name), "utf8").replace(/\r\n/g, "\n"); } catch {}
  if (a !== b) { drift++; if (!check) copyFileSync(join(from, name), join(to, name)); console.log(`${check ? "DRIFT" : "updated"} ${name}`); }
}
if (check && drift) { console.error("schema copies differ from the Python openbooks package: run `pnpm sync-schema`"); process.exit(1); }
