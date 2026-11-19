import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import { clearThreads, deleteThread, getThread, listThreads, saveThread } from "@/lib/store";
import { clearSessionFiles, forgetThreadFiles, recallFile, rememberFiles } from "@/lib/session-files";
import type { RefusedDoc, Thread } from "@/lib/types";

const t = (id: string, updatedAt: number): Thread => ({ id, title: id, createdAt: 0, updatedAt, turns: [] });

describe("thread store", () => {
  it("saves, lists newest first, deletes and clears", async () => {
    await clearThreads();
    await saveThread(t("old", 1));
    await saveThread(t("new", 2));
    expect((await listThreads()).map((x) => x.id)).toEqual(["new", "old"]);
    await saveThread({ ...t("old", 3), title: "renamed" });
    expect((await listThreads()).map((x) => x.id)).toEqual(["old", "new"]);
    expect((await getThread("old"))?.title).toBe("renamed");
    await deleteThread("old");
    expect(await getThread("old")).toBeUndefined();
    await clearThreads();
    expect(await listThreads()).toEqual([]);
  });

  it("recovers an interrupted run and incomplete answer while preserving confirmed results", async () => {
    await clearThreads();
    const refused: RefusedDoc = {
      schema_version: "openbooks.v1", status: "refused", data: null,
      error: { code: "BALANCE_MISMATCH", message: "Amounts do not reconcile", file_sha256: "abc" },
    };
    await saveThread({
      ...t("interrupted", 3),
      turns: [
        {
          kind: "run", id: "run", at: 1, state: "running", sourceTurnId: "source",
          files: [
            { index: 0, name: "refused.csv", size: 1, stages: ["parse"], state: "done", doc: refused, params: {} },
            { index: 1, name: "unfinished.csv", size: 2, stages: ["detect"], state: "running", params: { opening: "0.00100" } },
            { index: 2, name: "unstarted.csv", size: 2, stages: [], state: "queued", params: {} },
          ],
        },
        { kind: "answer", id: "answer", at: 2, state: "streaming", text: "Partial answer", tools: [] },
      ],
    });
    const [thread] = await listThreads();
    expect(thread?.turns).toMatchObject([
      { state: "error", files: [
        { state: "done", doc: refused },
        { state: "interrupted", stages: ["detect"], params: { opening: "0.00100" } },
        { state: "interrupted" },
      ] },
      { state: "error", text: "Partial answer" },
    ]);
  });

  it("drops retained source files for the deleted thread only", () => {
    const file = new File(["data"], "bank.csv");
    rememberFiles("source", [file]);
    rememberFiles("another-source", [file]);
    forgetThreadFiles({
      ...t("deleted", 1),
      turns: [{ kind: "user-run", id: "source", at: 1, files: [], params: {} }],
    });
    expect(recallFile("source", 0)).toBeUndefined();
    expect(recallFile("another-source", 0)).toBe(file);
    clearSessionFiles();
    expect(recallFile("another-source", 0)).toBeUndefined();
  });
});
