import { fileURLToPath } from "node:url";

try {
  const here = fileURLToPath(import.meta.url);
  if (!here.split(/[\\/]/).includes("node_modules")) process.exit(0);
  if (process.env.OPENBOOKS_SKIP_PYTHON) process.exit(0);

  const { installEngine } = await import("../dist/install-engine.js");
  const r = await installEngine({ scan: true, log: (l) => console.log(`openbooks: ${l}`) });
  console.log(`openbooks: ${r.detail}`);
  if (r.status === "failed") {
    console.log(`openbooks: the JavaScript packages are installed, but the Python engine is not.`);
    if (r.hint) console.log(`openbooks: ${r.hint}`);
    console.log(`openbooks: you can retry any time with: npx openbooks install-engine --scan`);
  }
} catch (e) {
  console.log(`openbooks: skipped the Python engine step (${e instanceof Error ? e.message : e}). Run: npx openbooks install-engine --scan`);
}
process.exit(0);
