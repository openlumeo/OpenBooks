import { afterEach, describe, expect, it, vi } from "vitest";
import { ask, predictRoles, runFiles } from "@/lib/engine-client";

const input = () => [new File(["data"], "bank.csv")];
const question = { question: "What is the balance?", history: [], docs: [] };
const mockBody = (body: string) => vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body)));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

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

  it("resumes polling a run after a gateway timeout without uploading again", async () => {
    vi.useFakeTimers();
    const fetch = vi.fn()
      .mockResolvedValueOnce(Response.json({ accepted: true }, { status: 202 }))
      .mockResolvedValueOnce(Response.json({ events: [{ event: "file.started", data: { index: 0, name: "bank.csv", size: 4 } }], cursor: 1, done: false }))
      .mockResolvedValueOnce(new Response(null, { status: 504 }))
      .mockResolvedValueOnce(Response.json({ events: [{ event: "run.done", data: { released: 1, refused: 0 } }], cursor: 2, done: true }));
    vi.stubGlobal("fetch", fetch);
    const result = Array.fromAsync(runFiles(input(), {}, {}));
    await vi.runAllTimersAsync();
    await expect(result).resolves.toMatchObject([{ type: "started" }, { type: "finished", released: 1 }]);
    expect(fetch.mock.calls.map(([path]) => path)).toEqual(["/api/runs", "/api/runs?cursor=0", "/api/runs?cursor=1", "/api/runs?cursor=1"]);
    expect(fetch.mock.calls[1]?.[1].headers).toEqual(fetch.mock.calls[0]?.[1].headers);
  });
});

it("polls the model reading with the same private job key", async () => {
  vi.useFakeTimers();
  const reading = { schema_version: "openbooks.roles.v1", summary: { tokens: 24 } };
  const fetch = vi.fn()
    .mockResolvedValueOnce(Response.json({ accepted: true }, { status: 202 }))
    .mockResolvedValueOnce(Response.json({ events: [], cursor: 0, done: false }))
    .mockResolvedValueOnce(Response.json({ events: [{ event: "roles", data: reading }], cursor: 1, done: true }));
  vi.stubGlobal("fetch", fetch);
  const result = predictRoles(new File(["scan"], "bank.jpeg"));
  await vi.runAllTimersAsync();
  await expect(result).resolves.toEqual(reading);
  expect(fetch.mock.calls[1]?.[1].headers).toEqual(fetch.mock.calls[0]?.[1].headers);
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
