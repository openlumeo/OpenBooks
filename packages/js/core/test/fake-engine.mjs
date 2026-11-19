// A stand-in for `python`: invoked as `node fake-engine.mjs -m openbooks_core <command> ...` and misbehaving on demand
// (FAKE_MODE) so the wrapper's error handling can be tested without breaking a real engine.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";
import { basename, dirname, join } from "node:path";

const args = process.argv.slice(2);
const mode = process.env.FAKE_MODE ?? "ok";
const cmd = args[2];
const info = { name: "openbooks-core", version: "0.0.0-fake", schema_version: "openbooks.v1", layout_api: mode === "old" ? 0 : 1,
               python: "3.12.0", layouts: [], known_layouts: [], frontends: [], linker: false };

if (cmd === "engine-info") {
  if (mode === "no_module") { console.error("No module named openbooks_core"); process.exit(1); }
  console.log(JSON.stringify(info));
  process.exit(0);
}
if (cmd !== "run") process.exit(2);

const out = args[args.indexOf("--out") + 1];
const files = args.slice(args.findIndex((a, i) => i > 3 && !a.startsWith("--") && args[i - 1] !== "--out" && args[i - 1] !== "--currency" && args[i - 1] !== "--opening") );
if (mode === "hang") setInterval(() => {}, 1000);
else if (mode === "crash") { console.error("Traceback (most recent call last):\n  boom"); process.exit(3); }
else if (mode === "garbage") { console.log("this is not json"); process.exit(0); }
else if (mode === "noisy") { process.stdout.write("x".repeat(5_000_000)); setInterval(() => {}, 1000); }
else {
  mkdirSync(out, { recursive: true });
  for (const f of files) {
    const sha = createHash("sha256").update(readFileSync(f)).digest("hex");
    const name = mode === "wrong_file" ? "0".repeat(64) : sha;
    const doc = mode === "bad_doc" ? { schema_version: "openbooks.v1", status: "refused", data: null }
      : { schema_version: "openbooks.v1", status: "refused", data: null, error: {
          code: "UNKNOWN_LAYOUT", message: basename(f), file_sha256: mode === "wrong_hash" ? "0".repeat(64) : sha,
        } };
    const target = join(out, `${name}.json`);
    writeFileSync(target, JSON.stringify(doc));
    const output = mode === "external_path" ? join(out, "alternate", `${name}.json`) : target;
    if (output !== target) {
      mkdirSync(dirname(output), { recursive: true });
      writeFileSync(output, JSON.stringify(doc));
    }
    console.log(JSON.stringify({ file: basename(f), status: "refused", code: "UNKNOWN_LAYOUT", output: mode === "bad_line" ? null : output }));
  }
  console.log(JSON.stringify({ engine: info }));
  process.exit(1);
}
