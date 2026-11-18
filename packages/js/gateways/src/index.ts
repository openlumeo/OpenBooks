import { runFile as coreRunFile, runFiles as coreRunFiles, type RunOptions, type RunResult } from "@openbooks/core";

export type { RunOptions, RunResult, Released, Refused } from "@openbooks/core";
export { isReleased, EngineError } from "@openbooks/core";

/** The layouts this package reads. A file that proves out under any other layout comes back refused (UNKNOWN_LAYOUT). */
export const LAYOUTS = ["stripe_balance.v1", "razorpay_settlement.v1", "paypal_activity.v1", "wise_statement.v1"] as const;

/** Payment gateway exports: Stripe, Razorpay, PayPal, Wise. PayPal and Wise are experimental. */
export const runFile = (file: string, opts: RunOptions = {}): Promise<RunResult> => coreRunFile(file, { ...opts, accept: LAYOUTS });
export const runFiles = (files: readonly string[], opts: RunOptions = {}): Promise<RunResult[]> => coreRunFiles(files, { ...opts, accept: LAYOUTS });
