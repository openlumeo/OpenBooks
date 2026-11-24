import { runFile as coreRunFile, runFiles as coreRunFiles, runJobs as coreRunJobs, type RunJob, type RunOptions, type RunResult } from "../core/index.js";

export type { DocumentOptions, RunJob, RunOptions, RunResult, Released, Refused } from "../core/index.js";
export { isReleased, EngineError } from "../core/index.js";

export const LAYOUTS = ["tds_26as.v1", "ais.v1", "fira.v1", "form_1099b.v1", "trial_balance.v1"] as const;

export const runFile = (file: string, opts: RunOptions = {}): Promise<RunResult> => coreRunFile(file, { ...opts, accept: LAYOUTS });
export const runFiles = (files: readonly string[], opts: RunOptions = {}): Promise<RunResult[]> => coreRunFiles(files, { ...opts, accept: LAYOUTS });
export const runJobs = (jobs: Iterable<RunJob> | AsyncIterable<RunJob>, opts: RunOptions = {}): AsyncGenerator<RunResult> => (
  coreRunJobs(jobs, { ...opts, accept: LAYOUTS })
);
