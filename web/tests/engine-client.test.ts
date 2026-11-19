import { afterEach, describe, expect, it, vi } from "vitest";
import { ask, runFiles } from "@/lib/engine-client";

const input = () => [new File(["data"], "bank.csv")];
const question = { question: "What is the balance?", history: [], docs: [] };
const mockBody = (body: string) => vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));

afterEach(() => vi.unstubAllGlobals());

describe("run client", () => {
  it("requires the batch completion marker after yielding individual results", async () => {
    const doc = { status: "refused", error: { code: "BALANCE_MISMATCH" } };
    mockBody(`event: file.done\ndata: ${JSON.stringify({ index: 0, doc })}\n\n`);
    const stream = runFiles(input(), {}, {});
    await expect(stream.next()).resolves.toMatchObject({ value: { type: "done", index: 0, doc } });
    await expect(stream.next()).rejects.toThrow("before the engine confirmed");
  });

  it("completes on run.done", async () => {
    mockBody('event: run.done\ndata: {"released":1,"refused":0}\n\n');
    const stream = runFiles(input(), {}, {});
    await expect(stream.next()).resolves.toMatchObject({ value: { type: "finished", released: 1, refused: 0 } });
    await expect(stream.next()).resolves.toMatchObject({ done: true });
  });

  it("surfaces engine errors", async () => {
    mockBody('event: run.error\ndata: {"message":"Engine failed."}\n\n');
    await expect(runFiles(input(), {}, {}).next()).rejects.toThrow("Engine failed.");
  });
});

describe("ask client", () => {
  it("yields partial text but reports a premature disconnect", async () => {
    mockBody('{"type":"text","text":"Partial"}\n');
    const stream = ask(question);
    await expect(stream.next()).resolves.toMatchObject({ value: { type: "text", text: "Partial" } });
    await expect(stream.next()).rejects.toThrow("before the answer completed");
  });

  it("distinguishes a done response from an error followed by done", async () => {
    mockBody('{"type":"done"}\n');
    const stream = ask(question);
    await expect(stream.next()).resolves.toMatchObject({ value: { type: "done" } });
    await expect(stream.next()).resolves.toMatchObject({ done: true });

    mockBody('{"type":"error","message":"Lookup failed."}\n{"type":"done"}\n');
    await expect(ask(question).next()).rejects.toThrow("Lookup failed.");
  });
});
