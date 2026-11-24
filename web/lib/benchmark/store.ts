import type { Scores } from "@/lib/benchmark/score";

export type Query = (text: string, params?: unknown[]) => Promise<Record<string, unknown>[]>;

export type StoredSubmission = {
  runId: string;
  provider: string;
  modelName: string;
  taskSet: string;
  tasksDigest: string;
  kitVersion: string;
  scores: Scores;
  engineOutcomes: { id: string; engine_outcomes: unknown[] }[];
};

export type LeaderboardEntry = {
  id: string;
  provider: string;
  model: string;
  taskSet: string;
  overall: number;
  releaseAccuracy: number;
  fieldAccuracy: number;
  efficiency: number;
  safety: number;
  criticalErrors: number;
  createdAt: string;
};

export const LEADERBOARD_DEFAULT_LIMIT = 50;
export const LEADERBOARD_MAX_LIMIT = 100;

const LEADERBOARD_SQL = `
  SELECT id, provider, model_name, task_set, overall, release_accuracy, field_accuracy,
         efficiency, safety, critical_errors, created_at
    FROM (
      SELECT DISTINCT ON (provider, model_name)
             id, provider, model_name, task_set, overall, release_accuracy, field_accuracy,
             efficiency, safety, critical_errors, created_at
        FROM public.benchmark_submissions
       ORDER BY provider, model_name, overall DESC, created_at ASC
    ) best
   ORDER BY overall DESC, created_at ASC
   LIMIT $1`;

function clampLimit(limit: number): number {
  if (!Number.isFinite(limit)) return LEADERBOARD_DEFAULT_LIMIT;
  return Math.min(Math.max(Math.trunc(limit), 1), LEADERBOARD_MAX_LIMIT);
}

function toIso(value: unknown): string {
  return new Date(value as string | Date).toISOString();
}

export function createBenchmarkStore(query: Query) {
  return {
    async insert(record: StoredSubmission): Promise<{ id: string } | null> {
      const rows = await query(
        `INSERT INTO public.benchmark_submissions
           (run_id, provider, model_name, task_set, tasks_digest, kit_version,
            release_accuracy, field_accuracy, efficiency, safety, overall,
            critical_errors, engine_outcomes)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)
         ON CONFLICT (run_id) DO NOTHING
         RETURNING id`,
        [
          record.runId,
          record.provider,
          record.modelName,
          record.taskSet,
          record.tasksDigest,
          record.kitVersion,
          record.scores.release_accuracy,
          record.scores.field_accuracy,
          record.scores.efficiency,
          record.scores.safety,
          record.scores.overall,
          record.scores.critical_errors.length,
          JSON.stringify(record.engineOutcomes),
        ],
      );
      const id = rows[0]?.id;
      return typeof id === "string" ? { id } : null;
    },
    async leaderboard(limit: number = LEADERBOARD_DEFAULT_LIMIT): Promise<LeaderboardEntry[]> {
      const rows = await query(LEADERBOARD_SQL, [clampLimit(limit)]);
      return rows.map((row) => ({
        id: String(row.id),
        provider: String(row.provider),
        model: String(row.model_name),
        taskSet: String(row.task_set),
        overall: Number(row.overall),
        releaseAccuracy: Number(row.release_accuracy),
        fieldAccuracy: Number(row.field_accuracy),
        efficiency: Number(row.efficiency),
        safety: Number(row.safety),
        criticalErrors: Number(row.critical_errors),
        createdAt: toIso(row.created_at),
      }));
    },
  };
}

export type BenchmarkStore = ReturnType<typeof createBenchmarkStore>;
