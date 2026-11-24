import { describe, expect, it } from "vitest";
import fixture from "./fixtures/benchmark-parity.json";
import { scoreBundle, scoreTask, tasksDigest } from "@/lib/benchmark/score";

type ParityCase = {
  name: string;
  kind: "task" | "bundle" | "digest";
  task_result: unknown;
  expected: unknown;
  python_score: unknown;
};

const cases = fixture as unknown as ParityCase[];

function runCase(parityCase: ParityCase): unknown {
  if (parityCase.kind === "task") return scoreTask(parityCase.task_result, parityCase.expected);
  if (parityCase.kind === "bundle") {
    return scoreBundle(parityCase.task_result as Record<string, unknown> | null, parityCase.expected);
  }
  const files = parityCase.task_result as Record<string, string>;
  const bytes = Object.fromEntries(
    Object.entries(files).map(([id, text]) => [id, new TextEncoder().encode(text)]),
  );
  return tasksDigest(bytes);
}

describe("Python parity fixture", () => {
  it("covers at least 120 scoring cases with every kind present", () => {
    const scoring = cases.filter((parityCase) => parityCase.kind !== "digest");
    expect(scoring.length).toBeGreaterThanOrEqual(120);
    expect(new Set(cases.map((parityCase) => parityCase.kind))).toEqual(new Set(["task", "bundle", "digest"]));
  });

  it.each(cases.map((parityCase) => [parityCase.name, parityCase] as const))("%s matches score.py", (_name, parityCase) => {
    expect(runCase(parityCase)).toEqual(parityCase.python_score);
  });
});
