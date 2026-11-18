import { runFile as coreRunFile, runFiles as coreRunFiles, type RunOptions, type RunResult } from "@openbooks/core";

export type { RunOptions, RunResult, Released, Refused } from "@openbooks/core";
export { isReleased, EngineError } from "@openbooks/core";

/** The layouts this package reads. A file that proves out under any other layout comes back refused (UNKNOWN_LAYOUT). */
export const LAYOUTS = ["tds_26as.v1", "ais.v1", "fira.v1", "form_1099b.v1", "trial_balance.v1"] as const;

/** Tax and ledger documents: Form 26AS, AIS, FIRA, Form 1099-B, trial balance. All experimental. */
export const runFile = (file: string, opts: RunOptions = {}): Promise<RunResult> => coreRunFile(file, { ...opts, accept: LAYOUTS });
export const runFiles = (files: readonly string[], opts: RunOptions = {}): Promise<RunResult[]> => coreRunFiles(files, { ...opts, accept: LAYOUTS });
