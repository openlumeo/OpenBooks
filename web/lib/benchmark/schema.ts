import { z } from "zod";

export const BENCH_SCHEMA = "openbooks.bench.v1";
export const PROVIDERS = ["anthropic", "openai", "gemini", "compat"] as const;
export const SUBMIT_MAX_BYTES = 256 * 1024;
export const MAX_TASKS = 200;
export const MAX_FINAL_ANSWER = 8000;
export const MAX_ID = 80;
export const MAX_FIELD_TEXT = 200;
export const MAX_ENGINE_FIELDS = 40;
export const MAX_ENGINE_OUTCOMES = 50;
const TASK_ID = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;
const SHA256_HEX = /^[0-9a-f]{64}$/;

const fieldValue = z.union([
  z.string().max(MAX_FIELD_TEXT),
  z.number().finite(),
  z.boolean(),
  z.null(),
]);

const engineOutcome = z.object({
  layout: z.string().min(1).max(MAX_ID),
  status: z.enum(["released", "refused"]),
  refusal_code: z.string().max(MAX_ID).nullable(),
  fields: z.record(z.string().max(MAX_ID), fieldValue).refine(
    (fields) => Object.keys(fields).length <= MAX_ENGINE_FIELDS,
    { message: "too many fields" },
  ),
});

const taskResult = z.object({
  id: z.string().min(1).max(MAX_ID).regex(TASK_ID),
  final_answer: z.string().max(MAX_FINAL_ANSWER),
  tool_calls: z.number().int().min(0).max(10_000),
  input_tokens: z.number().int().min(0).max(100_000_000),
  output_tokens: z.number().int().min(0).max(100_000_000),
  elapsed_s: z.number().min(0).max(86_400),
  engine_outcomes: z.array(engineOutcome).max(MAX_ENGINE_OUTCOMES),
  error: z.string().max(2000).nullable(),
});

export const submissionBundleSchema = z.object({
  schema: z.literal(BENCH_SCHEMA),
  kit_version: z.string().min(1).max(32),
  run_id: z.uuid(),
  created_at: z.iso.datetime({ offset: true }),
  model: z.object({
    provider: z.enum(PROVIDERS),
    name: z.string().min(1).max(120),
  }),
  tasks: z.array(taskResult).min(1).max(MAX_TASKS),
  scores: z.unknown().optional(),
  tasks_digest: z.string().regex(SHA256_HEX),
});

export type SubmissionBundle = z.infer<typeof submissionBundleSchema>;
export type SubmissionTask = SubmissionBundle["tasks"][number];
