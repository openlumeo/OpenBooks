import { runFile as coreRunFile, runFiles as coreRunFiles, type RunOptions, type RunResult } from "@lumeo_hq/openbooks-core";

export type { RunOptions, RunResult, Released, Refused } from "@lumeo_hq/openbooks-core";
export { isReleased, EngineError } from "@lumeo_hq/openbooks-core";

/** The layouts this package reads. A file that proves out under any other layout comes back refused (UNKNOWN_LAYOUT). */
export const LAYOUTS = ["bank_csv.v1", "ofx.v1", "mt940.v1", "bank_statement_pdf.v1"] as const;

/** Bank statements: bank CSV, OFX, MT940, and PDFs or scans (scans need the engine's [scan] extra: pip install 'openbooks[scan]'). */
export const runFile = (file: string, opts: RunOptions = {}): Promise<RunResult> => coreRunFile(file, { ...opts, accept: LAYOUTS });
export const runFiles = (files: readonly string[], opts: RunOptions = {}): Promise<RunResult[]> => coreRunFiles(files, { ...opts, accept: LAYOUTS });
