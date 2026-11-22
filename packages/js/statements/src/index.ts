import { runFile as coreRunFile, runFiles as coreRunFiles, runJobs as coreRunJobs, type RunJob, type RunOptions, type RunResult } from "@lumeo_hq/openbooks-core";

export type { DocumentOptions, RunJob, RunOptions, RunResult, Released, Refused } from "@lumeo_hq/openbooks-core";
export { isReleased, EngineError } from "@lumeo_hq/openbooks-core";

export const LAYOUTS = ["bank_csv.v1", "ofx.v1", "mt940.v1", "bank_statement_pdf.v1"] as const;

export const runFile = (file: string, opts: RunOptions = {}): Promise<RunResult> => coreRunFile(file, { ...opts, accept: LAYOUTS });
export const runFiles = (files: readonly string[], opts: RunOptions = {}): Promise<RunResult[]> => coreRunFiles(files, { ...opts, accept: LAYOUTS });
export const runJobs = (jobs: Iterable<RunJob> | AsyncIterable<RunJob>, opts: RunOptions = {}): AsyncGenerator<RunResult> => (
  coreRunJobs(jobs, { ...opts, accept: LAYOUTS })
);
