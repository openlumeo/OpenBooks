// Runs after `npm i @lumeo_hq/openbooks`: installs the Python engine so one npm command gives a working setup.
// Best effort and always exits 0: a failure here must never break `npm install`; `openbooks install-engine` retries it.
//   OPENBOOKS_SKIP_PYTHON=1   skip this step          npm i --ignore-scripts   skips it too
import { fileURLToPath } from "node:url";

try {
  const here = fileURLToPath(import.meta.url);
  // Only when installed from the registry. In a source checkout the engine comes from `pip install -e` (scripts/setup.py).
  if (!here.split(/[\\/]/).includes("node_modules")) process.exit(0);
  if (process.env.OPENBOOKS_SKIP_PYTHON) process.exit(0);

  const { installEngine } = await import("../dist/install-engine.js");
  const r = await installEngine({ log: (l) => console.log(`openbooks: ${l}`) });
  console.log(`openbooks: ${r.detail}`);
  if (r.status === "failed") {
    console.log(`openbooks: the JavaScript packages are installed, but the Python engine is not.`);
    if (r.hint) console.log(`openbooks: ${r.hint}`);
    console.log(`openbooks: you can retry any time with: npx openbooks install-engine`);
  }
} catch (e) {
  console.log(`openbooks: skipped the Python engine step (${e instanceof Error ? e.message : e}). Run: npx openbooks install-engine`);
}
process.exit(0);
