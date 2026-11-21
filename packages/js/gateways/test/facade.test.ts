import { describe, expect, it, vi, beforeEach } from "vitest";
import type { RunJob } from "@lumeo_hq/openbooks-core";

const core = vi.hoisted(() => ({
  runFile: vi.fn(), runFiles: vi.fn(), runJobs: vi.fn(),
}));
vi.mock("@lumeo_hq/openbooks-core", async (importOriginal) => ({ ...(await importOriginal<object>()), ...core }));

import { LAYOUTS, runFile, runFiles, runJobs } from "../src/index.js";

beforeEach(() => vi.clearAllMocks());

describe("gateways facade", () => {
  it("accepts only the payment-gateway layouts, and the list is not empty", () => {
    expect(LAYOUTS).toEqual(["stripe_balance.v1", "razorpay_settlement.v1", "paypal_activity.v1", "wise_statement.v1"]);
  });

  it("passes the gateway layouts as accept on every entry point and keeps caller options", async () => {
    core.runFile.mockResolvedValue("one");
    core.runFiles.mockResolvedValue(["many"]);
    await runFile("a.csv", { currency: "USD" });
    await runFiles(["a.csv", "b.csv"], { opening: "1.00" });
    expect(core.runFile).toHaveBeenCalledWith("a.csv", { currency: "USD", accept: LAYOUTS });
    expect(core.runFiles).toHaveBeenCalledWith(["a.csv", "b.csv"], { opening: "1.00", accept: LAYOUTS });
  });

  it("uses an empty options object when none are given", async () => {
    core.runFile.mockResolvedValue("one");
    await runFile("a.csv");
    expect(core.runFile).toHaveBeenCalledWith("a.csv", { accept: LAYOUTS });
  });

  it("forwards jobs to the core job runner with the same accept list", () => {
    const jobs: RunJob[] = [{ file: "a.csv" }];
    core.runJobs.mockReturnValue("generator");
    expect(runJobs(jobs, { ocr: false })).toBe("generator");
    expect(core.runJobs).toHaveBeenCalledWith(jobs, { ocr: false, accept: LAYOUTS });
  });

  it("does not mutate the caller's options object", async () => {
    core.runFile.mockResolvedValue("one");
    const opts = { currency: "INR" };
    await runFile("a.csv", opts);
    expect(opts).toEqual({ currency: "INR" });
  });
});
