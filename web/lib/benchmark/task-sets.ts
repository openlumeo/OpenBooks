import { z } from "zod";
import taskSetsFile from "./task-sets.json";
import { tasksDigest, type Expectation, type Outcome } from "./score";

export const EXPECTATION_OUTCOMES: readonly Outcome[] = ["released", "refused", "mixed"];

const taskIdSchema = z.string().min(1).max(80);

const taskSetSchema = z.object({
  label: z.string().min(1).max(80),
  tasks: z
    .record(taskIdSchema, z.object({ expectedRaw: z.string() }))
    .refine((tasks) => Object.keys(tasks).length > 0, { message: "tasks must not be empty" }),
});

export const taskSetsFileSchema = z.object({
  schema: z.literal("openbooks.bench.task-sets.v1"),
  sets: z.record(z.string().regex(/^[0-9a-f]{64}$/), taskSetSchema),
});

export type TaskSet = {
  label: string;
  taskIds: string[];
  expected: Record<string, Expectation>;
};

function isDict(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function parseExpectation(taskId: string, expectedRaw: string): Expectation {
  const parsed: unknown = JSON.parse(expectedRaw);
  const block = isDict(parsed) && Object.hasOwn(parsed, "expect") ? parsed.expect : parsed;
  if (!isDict(block) || !(EXPECTATION_OUTCOMES as readonly unknown[]).includes(block.outcome)) {
    throw new Error(`task ${taskId} has no valid outcome`);
  }
  return parsed as Expectation;
}

function buildTaskSet(digest: string, set: z.infer<typeof taskSetSchema>): TaskSet {
  const entries = Object.entries(set.tasks);
  const rawBytes = Object.fromEntries(
    entries.map(([id, { expectedRaw }]) => [id, new TextEncoder().encode(expectedRaw)]),
  );
  if (tasksDigest(rawBytes) !== digest) {
    throw new Error(`task set ${set.label} does not match its digest`);
  }
  const expected = Object.fromEntries(
    entries.map(([id, { expectedRaw }]) => [id, parseExpectation(id, expectedRaw)]),
  );
  return { label: set.label, taskIds: entries.map(([id]) => id), expected };
}

export function loadTaskSets(file: unknown): Readonly<Record<string, TaskSet>> {
  const parsed = taskSetsFileSchema.parse(file);
  return Object.fromEntries(
    Object.entries(parsed.sets).map(([digest, set]) => [digest, buildTaskSet(digest, set)]),
  );
}

export const knownTaskSets = loadTaskSets(taskSetsFile);
