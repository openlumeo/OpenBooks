import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { REFUSAL_CODES, SAMPLE_STATEMENT } from "./constants.js";

const SCHEMA_SPECIFIER = "@lumeo_hq/openbooks-core/schema/openbooks.v1.schema.json";

export function refusalGuide(): string {
  const rows = Object.entries(REFUSAL_CODES).map(([code, meaning]) => `- \`${code}\`: ${meaning}`).join("\n");
  return (
    "# Open Books refusal codes\n\n" +
    "A refusal is a completed decision: status refused, data null, a machine-readable code. " +
    "Never treat a refusal as a released document and never send its content onward.\n\n" +
    `${rows}\n`
  );
}

export async function releasedSchema(): Promise<string> {
  try {
    const path = createRequire(import.meta.url).resolve(SCHEMA_SPECIFIER);
    return JSON.stringify(JSON.parse(await readFile(path, "utf8")));
  } catch {
    return JSON.stringify({ error: "The output schema is not bundled with this installation." });
  }
}

export function sampleStatement(): string {
  return SAMPLE_STATEMENT;
}
