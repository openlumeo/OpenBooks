import { runFile as coreRunFile, runFiles as coreRunFiles, runJobs as coreRunJobs, type RunJob, type RunOptions, type RunResult } from "@lumeo_hq/openbooks-core";

export type { DocumentOptions, RunJob, RunOptions, RunResult, Released, Refused } from "@lumeo_hq/openbooks-core";
export { isReleased, EngineError } from "@lumeo_hq/openbooks-core";

/** The layouts this package reads. A file that proves out under any other layout comes back refused (UNKNOWN_LAYOUT). */
export const LAYOUTS = ["tds_26as.v1", "ais.v1", "fira.v1", "form_1099b.v1", "trial_balance.v1"] as const;

/** Tax and ledger documents: Form 26AS, AIS, FIRA, Form 1099-B, trial balance. All experimental. */
export const runFile = (file: string, opts: RunOptions = {}): Promise<RunResult> => coreRunFile(file, { ...opts, accept: LAYOUTS });
export const runFiles = (files: readonly string[], opts: RunOptions = {}): Promise<RunResult[]> => coreRunFiles(files, { ...opts, accept: LAYOUTS });
export const runJobs = (jobs: Iterable<RunJob> | AsyncIterable<RunJob>, opts: RunOptions = {}): AsyncGenerator<RunResult> => (
  coreRunJobs(jobs, { ...opts, accept: LAYOUTS })
);
