import { jsonError, NO_STORE_HEADERS } from "@/lib/http";
import { readSmallJson } from "@/lib/guards";
import { containsSecretLikeText } from "@/lib/benchmark/secrets";
import { scoreBundle, tasksDigestOk, type Scores } from "@/lib/benchmark/score";
import { BENCH_SCHEMA, SUBMIT_MAX_BYTES, submissionBundleSchema, type SubmissionBundle } from "@/lib/benchmark/schema";
import type { TaskSet } from "@/lib/benchmark/task-sets";
import type { BenchmarkStore } from "@/lib/benchmark/store";

export type SubmitDeps = {
  rateLimit: (req: Request) => Promise<Response | null>;
  store: Pick<BenchmarkStore, "insert">;
  taskSets: Readonly<Record<string, TaskSet>>;
};

const BODY_LIMIT_CODE = "body_limit";

function fail(status: number, error: string, message: string): Response {
  return jsonError(status, error, message, NO_STORE_HEADERS);
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

async function readBundle(req: Request): Promise<{ body: unknown } | { response: Response }> {
  const declared = req.headers.get("content-length");
  if (declared !== null && Number(declared) > SUBMIT_MAX_BYTES) {
    return { response: fail(413, "too_large", "The result bundle exceeds 256 KB.") };
  }
  try {
    return { body: await readSmallJson(req, SUBMIT_MAX_BYTES) };
  } catch (error: unknown) {
    if (error instanceof Error && error.message === BODY_LIMIT_CODE) {
      return { response: fail(413, "too_large", "The result bundle exceeds 256 KB.") };
    }
    return { response: fail(400, "invalid_json", "The request body is not valid JSON.") };
  }
}

function coversTaskSet(bundle: SubmissionBundle, set: TaskSet): boolean {
  const submitted = bundle.tasks.map((task) => task.id).sort();
  const expected = [...set.taskIds].sort();
  return submitted.length === expected.length && submitted.every((id, index) => id === expected[index]);
}

function publicScores(scores: Scores) {
  return {
    release_accuracy: scores.release_accuracy,
    field_accuracy: scores.field_accuracy,
    efficiency: scores.efficiency,
    safety: scores.safety,
    overall: scores.overall,
  };
}

export async function handleBenchmarkSubmit(req: Request, deps: SubmitDeps): Promise<Response> {
  const limited = await deps.rateLimit(req);
  if (limited) return limited;

  const read = await readBundle(req);
  if ("response" in read) return read.response;

  const raw = read.body;
  if (!isPlainObject(raw)) return fail(400, "invalid_bundle", "The body must be a result bundle object.");
  if (raw.schema !== BENCH_SCHEMA) return fail(400, "unsupported_schema", `Only ${BENCH_SCHEMA} is accepted.`);
  const { tasks_digest: _digest, ...unverified } = raw;
  if (containsSecretLikeText(unverified)) {
    return fail(400, "secret_like_content", "The bundle contains text that looks like an API key or token. Remove it and resubmit.");
  }

  const parsed = submissionBundleSchema.safeParse(raw);
  if (!parsed.success) return fail(400, "invalid_bundle", "The bundle does not match openbooks.bench.v1 limits.");
  const bundle = parsed.data;

  const set = tasksDigestOk(bundle.tasks_digest, deps.taskSets) ? deps.taskSets[bundle.tasks_digest] : undefined;
  if (!set) return fail(400, "unknown_task_set", "The tasks_digest does not match a known Open Books task set.");
  if (!coversTaskSet(bundle, set)) {
    return fail(400, "task_set_mismatch", "The bundle must contain every task of its task set exactly once.");
  }

  const scores = scoreBundle(bundle, set.expected);
  let stored: { id: string } | null;
  try {
    stored = await deps.store.insert({
      runId: bundle.run_id,
      provider: bundle.model.provider,
      modelName: bundle.model.name,
      taskSet: set.label,
      tasksDigest: bundle.tasks_digest,
      kitVersion: bundle.kit_version,
      scores,
      engineOutcomes: bundle.tasks.map((task) => ({ id: task.id, engine_outcomes: task.engine_outcomes })),
    });
  } catch {
    return fail(503, "benchmark_unavailable", "The leaderboard is unavailable. Please try again shortly.");
  }
  if (!stored) return fail(409, "duplicate_run", "This run_id was already submitted.");

  return Response.json(
    { id: stored.id, task_set: set.label, scores: publicScores(scores), critical_errors: scores.critical_errors.length },
    { status: 201, headers: NO_STORE_HEADERS },
  );
}
