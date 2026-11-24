import { describe, expect, it } from "vitest";
import type { RunResult } from "../src/core/index.js";
import type { DoctorReport } from "../src/doctor/index.js";
import { formatDoctorText, formatRunJson, formatRunText } from "../src/output.js";
import { parseMaxDocumentBytes, parseTimeout } from "../src/main.js";
import { EXIT } from "../src/main.js";

const released = (file: string): RunResult => ({
  kind: "released", file, document: { file: { layout_version: "bank.csv.v1" } } as never,
});
const refused = (file: string, code: string, message: string): RunResult => ({
  kind: "refused", file, code, message, internal: false, restricted: false, document: {} as never,
});
const report = (overrides: Partial<DoctorReport> = {}): DoctorReport => ({
  schema: "openbooks.doctor.v1", ok: true,
  summary: { pass: 2, warn: 0, fail: 0, skip: 0 },
  checks: [{ id: "node", status: "pass", detail: "v22" }, { id: "python", status: "pass", detail: "3.12" }],
  ...overrides,
});

describe("formatRunText", () => {
  it("prints nothing for no results", () => {
    expect(formatRunText([])).toBe("");
  });

  it("prints one line per file, in order, with the layout or the refusal code", () => {
    expect(formatRunText([released("a.csv"), refused("b.pdf", "PARSE_ERROR", "bad header")])).toBe(
      "a.csv: released bank.csv.v1\nb.pdf: refused PARSE_ERROR: bad header\n",
    );
  });

  it("keeps unicode file names and messages unchanged", () => {
    expect(formatRunText([refused("Résumé ₹.csv", "PARSE_ERROR", "支払い")])).toBe("Résumé ₹.csv: refused PARSE_ERROR: 支払い\n");
  });
});

describe("formatRunJson", () => {
  it("lists status and file for each result, with code and message only on refusals", () => {
    const parsed = JSON.parse(formatRunJson([released("a.csv"), refused("b.csv", "UNSUPPORTED_INPUT", "no")]));
    expect(parsed[0]).not.toHaveProperty("code");
    expect(parsed[0]).toMatchObject({ file: "a.csv", status: "released" });
    expect(parsed[1]).toMatchObject({ file: "b.csv", status: "refused", code: "UNSUPPORTED_INPUT", message: "no" });
  });

  it("is a two-space indented JSON array ending with a newline", () => {
    expect(formatRunJson([])).toBe("[]\n");
    expect(formatRunJson([released("a.csv")]).endsWith("\n  }\n]\n")).toBe(true);
  });
});

describe("formatDoctorText", () => {
  it("prints each check and a summary line that says OK", () => {
    expect(formatDoctorText(report())).toBe(
      "[pass] node: v22\n[pass] python: 3.12\n2 passed, 0 warnings, 0 failed, 0 skipped -> OK\n",
    );
  });

  it("adds a fix line only under failures and warnings, and says NOT OK on failure", () => {
    const text = formatDoctorText(report({
      ok: false,
      summary: { pass: 0, warn: 1, fail: 1, skip: 0 },
      checks: [
        { id: "engine", status: "fail", detail: "missing", fix: "pip install openbooks" },
        { id: "model", status: "warn", detail: "old", fix: "upgrade" },
        { id: "node", status: "pass", detail: "ok", fix: "ignored" },
      ],
    }));
    expect(text).toBe(
      "[fail] engine: missing\n       fix: pip install openbooks\n" +
      "[warn] model: old\n       fix: upgrade\n" +
      "[pass] node: ok\n" +
      "0 passed, 1 warnings, 1 failed, 0 skipped -> NOT OK\n",
    );
  });

  it("pads skipped status names to a fixed width", () => {
    expect(formatDoctorText(report({ checks: [{ id: "deep", status: "skip", detail: "not requested" }] })))
      .toContain("[skip] deep: not requested\n");
  });
});

describe("parseTimeout", () => {
  it("accepts whole milliseconds at both ends of the range", () => {
    expect(parseTimeout("1")).toBe(1);
    expect(parseTimeout("120000")).toBe(120000);
  });

  it.each(["0", "-5", "1.5", "abc", "", "2147483648"])("refuses %s as a usage error", (raw) => {
    expect(() => parseTimeout(raw)).toThrow(/--timeout/);
    try { parseTimeout(raw); } catch (e) { expect((e as { exitCode: number }).exitCode).toBe(EXIT.usage); }
  });
});

describe("parseMaxDocumentBytes", () => {
  it("accepts plain digits, including a very large value", () => {
    expect(parseMaxDocumentBytes("67108864")).toBe(67108864);
    expect(parseMaxDocumentBytes("9007199254740991")).toBe(Number.MAX_SAFE_INTEGER);
  });

  it.each(["0", "-1", "1e6", "0x10", "12 ", "9007199254740992", "1.0"])("refuses %s", (raw) => {
    expect(() => parseMaxDocumentBytes(raw)).toThrow(/--max-document-bytes/);
  });
});
