import { describe, expect, it } from "vitest";
import { EngineError } from "../src/errors.js";
import { parseMachineLines, splitBatches, type Input } from "../src/engine.js";

const input = (name: string, sha: string): Input => ({ path: `/in/${name}`, sha });
const RESULT = (file: string, status: "ok" | "refused" = "ok", code: string | null = null) =>
  JSON.stringify({ file, status, code, output: `/out/${file}.json` });

describe("splitBatches", () => {
  it("returns one empty batch for no inputs, so callers never see an undefined batch", () => {
    expect(splitBatches([])).toEqual([[]]);
  });

  it("keeps distinct content in a single batch in input order", () => {
    const inputs = [input("a.csv", "1"), input("b.csv", "2"), input("c.csv", "3")];
    expect(splitBatches(inputs)).toEqual([inputs]);
  });

  it("starts a new batch when the same bytes appear again, without losing any input", () => {
    const [a, b, aAgain] = [input("a.csv", "1"), input("b.csv", "2"), input("a-copy.csv", "1")];
    expect(splitBatches([a, b, aAgain])).toEqual([[a, b], [aAgain]]);
  });

  it("splits every repeat, including a run of identical files", () => {
    const same = ["x", "x", "x"].map((name) => input(`${name}.csv`, "9"));
    expect(splitBatches(same).map((batch) => batch.length)).toEqual([1, 1, 1]);
  });

  it("handles a large input list without dropping entries", () => {
    const many = Array.from({ length: 5000 }, (_, i) => input(`f${i}.csv`, String(i)));
    const batches = splitBatches(many);
    expect(batches).toHaveLength(1);
    expect(batches[0]).toHaveLength(5000);
  });
});

describe("parseMachineLines", () => {
  it("parses one result per line and skips a trailing engine-info line", () => {
    const stdout = `${RESULT("a.csv")}\n${RESULT("b.csv", "refused", "PARSE_ERROR")}\n{"engine":"openbooks","version":"0.2.0"}\n`;
    const lines = parseMachineLines(stdout);
    expect(lines.map((line) => line.file)).toEqual(["a.csv", "b.csv"]);
    expect(lines[1]).toMatchObject({ status: "refused", code: "PARSE_ERROR" });
  });

  it("accepts CRLF line endings and blank lines", () => {
    expect(parseMachineLines(`${RESULT("a.csv")}\r\n\r\n${RESULT("b.csv")}\r\n`)).toHaveLength(2);
  });

  it("returns nothing for empty output", () => {
    expect(parseMachineLines("")).toEqual([]);
    expect(parseMachineLines("\n\n")).toEqual([]);
  });

  it("keeps unicode file names intact", () => {
    const [line] = parseMachineLines(RESULT("Résumé-₹-支払い.csv"));
    expect(line?.file).toBe("Résumé-₹-支払い.csv");
  });

  it("rejects malformed JSON as bad output", () => {
    expect(() => parseMachineLines(`${RESULT("a.csv")}\n{not json`)).toThrow(EngineError);
    expect(() => parseMachineLines("{not json")).toThrow(/not JSON lines/);
  });

  it("rejects a result that does not match the contract, naming the line", () => {
    const bad = JSON.stringify({ file: "a.csv", status: "ok", code: "PARSE_ERROR", output: "/o" });
    expect(() => parseMachineLines(`${RESULT("a.csv")}\n${bad}`)).toThrow(/line 2/);
  });

  it("does not skip an engine-looking object that is not the final line", () => {
    expect(() => parseMachineLines(`{"engine":"x"}\n${RESULT("a.csv")}`)).toThrow(/line 1/);
  });
});
