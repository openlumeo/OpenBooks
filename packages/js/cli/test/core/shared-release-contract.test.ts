import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { isReleased, runFile } from "../../src/core/index.js";

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, "../../../../..");
const shared = join(repo, "packages/py/openbooks/tests/fixtures/shared");
const venvPython = join(repo, ".venv", process.platform === "win32" ? "Scripts/python.exe" : "bin/python");
const realPython = process.env.OPENBOOKS_PYTHON ?? (existsSync(venvPython) ? venvPython : undefined);

type Params = { currency?: string; opening?: string; date_order?: "dmy" | "ymd" };
type Case = {
  id: string;
  file: string;
  params: Params;
  status: "ok" | "refused";
  code: string | null;
  layout_version?: string;
  assertion_independent?: boolean[];
  coverage?: Record<string, number>;
};
const cases = (JSON.parse(readFileSync(join(shared, "release_contract.json"), "utf8")) as { cases: Case[] }).cases;

function optionsFor(params: Params) {
  return {
    python: realPython!,
    ...(params.currency !== undefined ? { currency: params.currency } : {}),
    ...(params.opening !== undefined ? { opening: params.opening } : {}),
    ...(params.date_order !== undefined ? { dateOrder: params.date_order } : {}),
  };
}

describe.skipIf(!realPython)("shared release contract with the real engine", () => {
  it.each(cases)("$id", async (c) => {
    const r = await runFile(join(shared, c.file), optionsFor(c.params));
    expect(isReleased(r) ? "ok" : "refused").toBe(c.status);
    expect(r.kind === "refused" ? r.code : null).toBe(c.code);
    if (!isReleased(r) || c.status !== "ok") return;
    expect(r.document.file.layout_version).toBe(c.layout_version);
    expect(r.document.assertions.map((a) => a.independent)).toEqual(c.assertion_independent);
    expect(r.document.coverage).toEqual(c.coverage);
  });
});
