import "fake-indexeddb/auto";
import { describe, expect, it } from "vitest";
import { clearThreads, deleteThread, getThread, listThreads, saveThread } from "@/lib/store";
import type { Thread } from "@/lib/types";

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
});
