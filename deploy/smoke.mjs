import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { basename } from "node:path";

const args = process.argv.slice(2);
const engineOnly = args[0] === "--engine";
if (engineOnly) args.shift();
const [address, image] = args;
if (!address) throw new Error("Usage: node deploy/smoke.mjs [--engine] <URL> [statement image]");
const base = new URL(address);
const endpoint = {
  catalog: engineOnly ? "/v1" : "/api/engine",
  requests: engineOnly ? "/v1" : "/api",
};

async function request(path, body) {
  const response = await fetch(new URL(path, base), {
    ...(body ? { method: "POST", body } : {}),
    signal: AbortSignal.timeout(180_000),
  });
  assert(response.ok, `${path} returned HTTP ${response.status}`);
  return response;
}

const health = await (await request(`${endpoint.catalog}/health`)).json();
assert(health.model_ready && health.ocr_available && health.model_identity, "The engine must have OCR and the calibrated model");
const pdf = await (await request(`${endpoint.catalog}/samples/ok_pdf_text`)).blob();
const params = { currency: "INR", date_order: "dmy", model: true };

const upload = new FormData();
upload.append("files", pdf, "statement.pdf");
upload.append("params", JSON.stringify(params));
const run = await request(`${endpoint.requests}/runs`, upload);
assert.match(run.headers.get("content-type") ?? "", /^text\/event-stream/);
const events = [...(await run.text()).matchAll(/^event: (.+)\r?\ndata: (.+)$/gm)]
  .map(([, type, json]) => ({ type, payload: JSON.parse(json) }));
const doc = events.find(({ type }) => type === "file.done")?.payload.doc;
assert.equal(events.at(-1)?.type, "run.done");
assert.equal(doc?.status, "ok", doc?.error?.message);
assert.deepEqual(doc.file.model, health.model_identity, "The run must record the deployed model");
assert.equal(doc.data.transactions.length, 10);
assert.equal(doc.data.transactions[0].date, "2026-01-01");
assert.deepEqual(doc.data.transactions[0].amount, { amount: "2226.70", currency: "INR" });
console.log(`Statement released with ${doc.data.transactions.length} verified transactions and model provenance.`);

const modelUpload = new FormData();
modelUpload.append("file", image ? new Blob([await readFile(image)]) : pdf, image ? basename(image) : "statement.pdf");
modelUpload.append("params", JSON.stringify(params));
const reading = await (await request(`${endpoint.requests}/roles`, modelUpload)).json();
assert.equal(reading.schema_version, "openbooks.roles.v1");
assert.equal(reading.method, image ? "ocr" : "pdf_text");
assert.deepEqual(reading.model, health.model_identity);
assert(reading.summary.tokens > 0, "The model must return predictions");
if (image) assert(reading.pages.some((page) => page.tokens.some((token) => typeof token.ocr_confidence === "number")));
console.log(`Model read ${reading.summary.tokens} words using ${reading.method} on ${reading.summary.device}.`);
