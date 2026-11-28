import { describe, expect, it } from "vitest";
import { REFUSAL_CODES as GENERATED } from "../../src/core/generated/refusal-codes.js";
import { validateRefusal } from "../../src/core/validate.js";
import { REFUSAL_CODES } from "../../src/mcp/constants.js";

const SHA = "a".repeat(64);

describe("refusal codes", () => {
  it("share one generated registry across the MCP surface", () => {
    expect(REFUSAL_CODES).toBe(GENERATED);
    expect(Object.keys(GENERATED)).toEqual(expect.arrayContaining(["PARSE_ERROR", "UNKNOWN_LAYOUT", "LOW_CONFIDENCE"]));
  });

  it("treat an unknown code as data, not as an error", () => {
    const refusal = { schema_version: "openbooks.v1", status: "refused", data: null, error: { code: "FUTURE_CODE", message: "m", file_sha256: SHA } };
    expect(() => validateRefusal(refusal)).not.toThrow();
    expect(Object.hasOwn(REFUSAL_CODES, "FUTURE_CODE")).toBe(false);
  });
});
