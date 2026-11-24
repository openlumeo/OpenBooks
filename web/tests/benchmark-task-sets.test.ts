import { describe, expect, it } from "vitest";
import committed from "@/lib/benchmark/task-sets.json";
import { knownTaskSets, loadTaskSets } from "@/lib/benchmark/task-sets";
import { tasksDigest } from "@/lib/benchmark/score";

const encoder = new TextEncoder();
const EXPECTED_DIGEST = "ce146a1e931013fa21c0f2ae96c091d8a21ba9b8ed59db18f8cf7e2fe58d6bef";

type CommittedSets = {
  schema: string;
  sets: Record<string, { label: string; tasks: Record<string, { expectedRaw: string }> }>;
};

const file = committed as unknown as CommittedSets;

function digestOfRaw(tasks: Record<string, { expectedRaw: string }>): string {
  return tasksDigest(
    Object.fromEntries(Object.entries(tasks).map(([id, { expectedRaw }]) => [id, encoder.encode(expectedRaw)])),
  );
}

describe("committed bench task set", () => {
  it("names the expected digest and holds the 36 bench tasks", () => {
    expect(Object.keys(file.sets)).toEqual([EXPECTED_DIGEST]);
    expect(Object.keys(file.sets[EXPECTED_DIGEST]?.tasks ?? {})).toHaveLength(36);
    expect(file.sets[EXPECTED_DIGEST]?.label).toBe("openbooks-bench-1");
  });

  it("has a digest that matches a recompute over its own raw expected texts", () => {
    for (const [digest, set] of Object.entries(file.sets)) {
      expect(digestOfRaw(set.tasks)).toBe(digest);
    }
  });

  it("is accepted by the loader and exposes parsed expectations", () => {
    const sets = loadTaskSets(committed);
    expect(sets[EXPECTED_DIGEST]?.label).toBe("openbooks-bench-1");
    expect(sets[EXPECTED_DIGEST]?.taskIds).toHaveLength(36);
    expect(knownTaskSets).toEqual(sets);
    const multi = sets[EXPECTED_DIGEST]?.expected["multi-mixed-csv-and-tampered"];
    expect(multi?.outcome).toBe("mixed");
  });

  it("is rejected by the loader once any raw expected text is altered", () => {
    const tampered = structuredClone(file);
    const set = tampered.sets[EXPECTED_DIGEST];
    const first = set ? Object.keys(set.tasks)[0] : undefined;
    if (set && first !== undefined) {
      set.tasks[first] = { expectedRaw: `${set.tasks[first]?.expectedRaw ?? ""} ` };
    }
    expect(() => loadTaskSets(tampered)).toThrow(/digest/);
  });
});
