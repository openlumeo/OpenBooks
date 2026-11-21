import { describe, expect, it } from "vitest";
import { readSmallJson, rejectNonMultipart, rejectOversize } from "@/lib/guards";

function req(headers: Record<string, string>): Request {
  return new Request("http://localhost/api/x", { method: "POST", headers });
}

describe("rejectOversize", () => {
  it("lets a request within the limit through", () => {
    expect(rejectOversize(req({ "content-length": "100" }), 1000)).toBeNull();
  });
  it("rejects a request over the limit with 413", async () => {
    const res = rejectOversize(req({ "content-length": "1001" }), 1000);
    expect(res?.status).toBe(413);
    expect(await res?.json()).toMatchObject({ error: "too_large" });
  });
  it("rejects a missing or malformed length with 411", () => {
    expect(rejectOversize(req({}), 1000)?.status).toBe(411);
    expect(rejectOversize(req({ "content-length": "abc" }), 1000)?.status).toBe(411);
    expect(rejectOversize(req({ "content-length": "-5" }), 1000)?.status).toBe(411);
  });
});

describe("rejectOversize edge cases", () => {
  it("accepts a body exactly at the limit", () => {
    expect(rejectOversize(req({ "content-length": "1000" }), 1000)).toBeNull();
  });
  it("treats a chunked request without Content-Length as missing length (411)", () => {
    const chunked = new Request("http://localhost/api/x", {
      method: "POST",
      headers: { "transfer-encoding": "chunked" },
      body: new ReadableStream({ start: (c) => c.close() }),
      duplex: "half",
    } as RequestInit);
    expect(rejectOversize(chunked, 1000)?.status).toBe(411);
  });
  it("rejects a length written in exponent notation", () => {
    expect(rejectOversize(req({ "content-length": "1e3" }), 1000)?.status).toBe(411);
  });
});

describe("rejectNonMultipart", () => {
  it("lets multipart uploads through", () => {
    expect(rejectNonMultipart("multipart/form-data; boundary=x")).toBeNull();
  });
  it("answers any other media type with 415", async () => {
    const res = rejectNonMultipart("application/json");
    expect(res?.status).toBe(415);
    expect(await res?.json()).toEqual({ error: "bad_request", message: "expected a multipart upload" });
  });
});

describe("readSmallJson", () => {
  function bodyOf(...chunks: string[]): Request {
    const encoder = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
        controller.close();
      },
    });
    return new Request("http://localhost/api/x", { method: "POST", body: stream, duplex: "half" } as RequestInit);
  }

  it("parses JSON assembled from several chunks", async () => {
    await expect(readSmallJson(bodyOf('{"a":', "1}"), 100)).resolves.toEqual({ a: 1 });
  });
  it("throws body_limit once the streamed bytes exceed the cap", async () => {
    await expect(readSmallJson(bodyOf("0123456789", "0123456789"), 15)).rejects.toThrow("body_limit");
  });
  it("accepts a body exactly at the cap", async () => {
    await expect(readSmallJson(bodyOf('"ok"'), 4)).resolves.toBe("ok");
  });
  it("throws invalid_json when the request has no body", async () => {
    const empty = new Request("http://localhost/api/x", { method: "POST" });
    await expect(readSmallJson(empty, 100)).rejects.toThrow("invalid_json");
  });
  it("throws a SyntaxError for malformed JSON", async () => {
    await expect(readSmallJson(bodyOf("{nope"), 100)).rejects.toThrow(SyntaxError);
  });
});
