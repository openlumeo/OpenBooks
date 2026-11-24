import { basename } from "node:path";
import { findEngine, runFile } from "../src/core/index.js";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Operations, type Doc } from "../src/mcp/operations.js";
import { call, encode, ENGINE, errorCode, refused, released, resultOf } from "./mcp/helpers.js";

vi.mock("../src/core/index.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../src/core/index.js")>()),
  runFile: vi.fn(),
  findEngine: vi.fn(),
}));

const runFileMock = vi.mocked(runFile);
const findEngineMock = vi.mocked(findEngine);

const BALANCED_DATA = {
  opening: "1000.00",
  accounts: [{ id: "acc1" }],
  transactions: [{ id: "t1" }, { id: "t2" }, { id: "t3" }],
  batches: [{ id: "b1", opening: "1000.00", closing: "1250.00", currency: "INR" }],
};

const bytes = (value: unknown): number => Buffer.byteLength(JSON.stringify(value));

const upload = (filename = "s.csv", content = "a,b\n1,2\n"): Doc => ({ filename, content_base64: encode(content) });

async function sample(args: Doc = {}): Promise<Doc> {
  return resultOf(await call(new Operations(), "process_sample", { opening: "1000.00", ...args }));
}

beforeEach(() => {
  runFileMock.mockReset();
  findEngineMock.mockReset();
  findEngineMock.mockResolvedValue(ENGINE);
  runFileMock.mockImplementation(async (file) => released(basename(file), { data: BALANCED_DATA }));
});

describe("detail tiers on process_sample", () => {
  it("omitted detail equals standard exactly", async () => {
    const omitted = await sample();
    const explicit = await sample({ detail: "standard" });
    expect(omitted).toEqual(explicit);
    expect(omitted).toHaveProperty("schema_version", "openbooks.v1");
    expect(omitted).toHaveProperty("counts");
  });

  it("orders verdict < standard < figures by JSON byte length for a released sample", async () => {
    const verdict = await sample({ detail: "verdict" });
    const figures = await sample({ detail: "figures" });
    const standard = await sample({ detail: "standard" });
    expect(bytes(verdict)).toBeLessThan(bytes(standard));
    expect(bytes(standard)).toBeLessThan(bytes(figures));
  });

  it("verdict is under 50% of full bytes on the fixture", async () => {
    const verdict = await sample({ detail: "verdict" });
    const full = await sample({ detail: "standard" });
    expect(bytes(verdict)).toBeLessThan(bytes(full) * 0.5);
  });

  it("verdict carries only status and engine_version with no balances or rows", async () => {
    const verdict = await sample({ detail: "verdict" });
    expect(Object.keys(verdict).sort()).toEqual(["engine_version", "status"]);
    expect(verdict).toEqual({ status: "released", engine_version: "9.9.9" });
    const text = JSON.stringify(verdict);
    expect(text).not.toContain("opening_balance");
    expect(text).not.toContain("closing_balance");
    expect(text).not.toContain("transactions");
    expect(text).not.toContain("1250.00");
  });

  it("figures adds counts, balances and currency from the first batch", async () => {
    const summary = await sample({ detail: "figures" });
    expect(summary).toEqual({
      status: "released",
      engine_version: "9.9.9",
      counts: { accounts: 1, transactions: 3, batches: 1, opening: 0 },
      opening_balance: "1000.00",
      closing_balance: "1250.00",
      currency: "INR",
    });
  });

  it("returns the typed refusal code at every tier and no figures at verdict tier", async () => {
    runFileMock.mockImplementation(async (file) => refused(basename(file), "BALANCE_MISMATCH", "totals differ"));

    const verdict = await sample({ detail: "verdict" });
    expect(verdict).toEqual({ status: "refused", engine_version: "9.9.9", code: "BALANCE_MISMATCH" });
    expect(verdict).not.toHaveProperty("counts");
    expect(verdict).not.toHaveProperty("opening_balance");

    const summary = await sample({ detail: "figures" });
    expect(summary).toEqual({ status: "refused", engine_version: "9.9.9", code: "BALANCE_MISMATCH" });

    const full = await sample({ detail: "standard" });
    expect(full).toHaveProperty("status", "refused");
    expect(full).toHaveProperty("error.code", "BALANCE_MISMATCH");
    expect(full).not.toHaveProperty("counts");
  });

  it("rejects an invalid detail value with INVALID_ARGUMENTS", async () => {
    const item = await call(new Operations(), "process_sample", { detail: "everything" });
    expect(errorCode(item)).toBe("INVALID_ARGUMENTS");
    expect(runFileMock).not.toHaveBeenCalled();
  });
});

describe("detail tiers on process_upload", () => {
  it("verdict tier omits figures for a released upload", async () => {
    const verdict = resultOf(await call(new Operations(), "process_upload", { ...upload(), detail: "verdict" }));
    expect(verdict).toEqual({ status: "released", engine_version: "9.9.9" });
  });

  it("rejects an invalid detail value with INVALID_ARGUMENTS", async () => {
    const item = await call(new Operations(), "process_upload", { ...upload(), detail: 1 });
    expect(errorCode(item)).toBe("INVALID_ARGUMENTS");
  });
});

describe("verify_many compact shape", () => {
  it("keeps the compact per-file shape by default", async () => {
    const result = resultOf(await call(new Operations(), "verify_many", { uploads: [upload("a.csv")] }));
    expect(result).toEqual({
      total: 1,
      ok: 1,
      refused: 0,
      error: 0,
      files: [{ name: "a.csv", status: "ok", rows: 3, assertions: 2 }],
    });
  });

  it("carries the refusal code for a refused file", async () => {
    runFileMock.mockImplementation(async (file) => refused(basename(file), "UNKNOWN_LAYOUT", "no layout"));
    const result = resultOf(await call(new Operations(), "verify_many", { uploads: [upload("bad.csv")] }));
    expect(result).toEqual({
      total: 1,
      ok: 0,
      refused: 1,
      error: 0,
      files: [{ name: "bad.csv", status: "refused", code: "UNKNOWN_LAYOUT" }],
    });
  });
});
