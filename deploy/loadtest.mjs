// Offered-rate benchmark for the inference engine. Open loop: requests start on schedule whether or not earlier ones
// finished, so rejections and queueing show up as such instead of slowing the offered rate.
//
//   node deploy/loadtest.mjs --engine http://10.30.0.2:8765 --mode sustained --rps 1,2,4 --duration 60 > bench.csv
//   node deploy/loadtest.mjs --engine http://127.0.0.1:8765 --mode burst --burst-requests 1000 --burst-window 5
//
// Modes: warmup (sequential, --warmup-requests, rows emitted), sustained (each --rps for --duration s), burst.
// Output: CSV on stdout (or --out), gate verdict on stderr; exit 1 when the promotion gate fails.
// Gate: every fixture (the packaged synthetic PDFs and scans) matches its expected release/refusal, and p95 of single-page
// requests stays under --max-p95-text-ms / --max-p95-scan-ms; error rate under --max-error-pct; optional --max-rss-mib.
// ponytail: the engine's /metrics supplies stage p95s, RSS and VRAM; against the public site (no /metrics) those are blank.
import { readFile, writeFile } from "node:fs/promises";
import { basename } from "node:path";
import { parseArgs } from "node:util";

// The engine rejects callers without its shared key when OPENBOOKS_ENGINE_KEY is set on the server.
const KEY_HEADER = process.env.OPENBOOKS_ENGINE_KEY ? { "x-openbooks-key": process.env.OPENBOOKS_ENGINE_KEY } : {};

const COLUMNS = "run_id,input_kind,page_bucket,offered_rps,completed_rps,in_flight,p50_ms,p95_ms,p99_ms,queue_p95_ms,ocr_p95_ms,model_p95_ms,peak_rss_mib,peak_vram_mib,rejected_pct,error_pct".split(",");
const { values: o } = parseArgs({
  options: {
    engine: { type: "string" }, mode: { type: "string", default: "sustained" }, rps: { type: "string", default: "1" },
    duration: { type: "string", default: "30" }, "burst-requests": { type: "string", default: "1000" },
    "burst-window": { type: "string", default: "5" }, "warmup-requests": { type: "string", default: "5" },
    "scan-share": { type: "string", default: "0.4" }, route: { type: "string", default: "runs" },
    image: { type: "string", multiple: true, default: [] }, "run-id": { type: "string" }, out: { type: "string" },
    "max-p95-text-ms": { type: "string", default: "2000" }, "max-p95-scan-ms": { type: "string", default: "8000" },
    "max-error-pct": { type: "string", default: "0" }, "max-rejected-pct": { type: "string", default: "100" },
    "max-rss-mib": { type: "string" }, "skip-fixtures": { type: "boolean", default: false },
  },
});
const USAGE = "Usage: node deploy/loadtest.mjs --engine <URL> [--mode warmup|sustained|burst] [--rps 1,2,4] ...";
if (!o.engine) {
  console.error(USAGE);
  process.exit(2);
}
if (!["runs", "roles"].includes(o.route)) {
  console.error("--route must be runs or roles");
  process.exit(2);
}
const base = new URL(o.engine);
const num = (k) => Number(o[k]);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const PARAMS = JSON.stringify({ currency: "INR", date_order: "dmy", model: true });

// ---- fixtures ----
const bucket = (pages) => (pages <= 1 ? "1" : pages <= 5 ? "2-5" : "6+");
const pageCount = (buf, name) => (/\.pdf$/i.test(name) ? Math.max(1, (buf.toString("latin1").match(/\/Type\s*\/Page\b/g) ?? []).length) : 1);
const kindOf = (name) => (/\.pdf$/i.test(name) ? "pdf_text" : "ocr");

async function loadFixtures() {
  const list = await (await fetch(new URL("/v1/samples", base), { headers: KEY_HEADER })).json();
  const out = [];
  for (const s of list.samples.filter((s) => /\.(pdf|png|jpe?g)$/i.test(s.filename))) {
    const buf = Buffer.from(await (await fetch(new URL(`/v1/samples/${s.id}`, base), { headers: KEY_HEADER })).arrayBuffer());
    out.push({ name: s.filename, buf, params: JSON.stringify({ ...s.params, currency: s.params?.currency ?? "INR" }),
      kind: kindOf(s.filename), pages: pageCount(buf, s.filename), expect: { status: s.expect_status, code: s.expect_code } });
  }
  for (const path of o.image) {
    const buf = await readFile(path);
    out.push({ name: basename(path), buf, params: PARAMS, kind: "ocr", pages: 1, expect: null });
  }
  if (!out.length) throw new Error("no PDF or image fixtures available");
  return out;
}

// ---- one request ----
async function fire(fx, id) {
  const t0 = performance.now();
  const fd = new FormData();
  fd.append(o.route === "runs" ? "files" : "file", new Blob([fx.buf]), fx.name);
  fd.append("params", fx.params);
  try {
    const res = await fetch(new URL(`/v1/${o.route}`, base), { method: "POST", body: fd, headers: { ...KEY_HEADER, "x-request-id": id }, signal: AbortSignal.timeout(180_000) });
    const text = await res.text();
    const ms = performance.now() - t0;
    if (res.status === 429 || res.status === 503) return { outcome: "rejected", ms };
    if (!res.ok) return { outcome: "error", ms };
    if (o.route === "roles") return { outcome: "ok", ms, status: "ok" };
    const done = [...text.matchAll(/^event: (.+)\r?\ndata: (.+)$/gm)].map(([, type, json]) => ({ type, payload: JSON.parse(json) }));
    const doc = done.find((e) => e.type === "file.done")?.payload.doc;
    if (!doc || done.at(-1)?.type !== "run.done") return { outcome: "error", ms };
    return { outcome: "ok", ms, status: doc.status, code: doc.error?.code };
  } catch {
    return { outcome: "error", ms: performance.now() - t0 };
  }
}

// ---- engine metrics (histogram deltas, RSS and VRAM peaks) ----
async function scrape() {
  try {
    const res = await fetch(new URL("/metrics", base), { headers: KEY_HEADER, signal: AbortSignal.timeout(5000) });
    if (!res.ok) return null;
    const m = { hist: {}, rss: 0, vram: 0 };
    for (const line of (await res.text()).split("\n")) {
      const g = line.match(/^(\w+)(?:\{(.*)\})? ([-+\d.eE]+|NaN)$/);
      if (!g) continue;
      const [, name, rawLabels = "", v] = g;
      if (name === "process_resident_memory_bytes") m.rss = Number(v);
      else if (name === "openbooks_cuda_max_allocated_bytes") m.vram = Number(v);
      else if (name === "openbooks_stage_seconds_bucket") {
        const l = Object.fromEntries([...rawLabels.matchAll(/(\w+)="([^"]*)"/g)].map((x) => [x[1], x[2]]));
        ((m.hist[`${l.stage}|${l.input_kind}`] ??= []).push([l.le === "+Inf" ? Infinity : Number(l.le), Number(v)]));
      }
    }
    return m;
  } catch {
    return null;
  }
}
// p95 (ms) from the difference of two cumulative histograms, linearly interpolated inside the bucket.
function histQuantile(before, after, key, q) {
  const a = after?.hist[key];
  if (!a) return "";
  const b = before?.hist[key] ?? [];
  const d = a.map(([le, c], i) => [le, c - (b[i]?.[1] ?? 0)]);
  const total = d.at(-1)[1];
  if (total <= 0) return "";
  const rank = q * total;
  let prevLe = 0, prevC = 0;
  for (const [le, c] of d) {
    if (c >= rank) return Math.round((Number.isFinite(le) ? prevLe + ((le - prevLe) * (rank - prevC)) / Math.max(c - prevC, 1e-9) : prevLe) * 1000);
    prevLe = le; prevC = c;
  }
  return "";
}
const pct = (sorted, q) => (sorted.length ? Math.round(sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)]) : "");

// ---- one measured phase ----
async function phase(runId, requests, offeredRps, picker) {
  const before = await scrape();
  let peakRss = 0, peakVram = 0, inFlight = 0, peakInFlight = 0, polling = true;
  const poll = (async () => {
    while (polling) {
      const m = await scrape();
      if (m) { peakRss = Math.max(peakRss, m.rss); peakVram = Math.max(peakVram, m.vram); }
      await sleep(1000);
    }
  })();
  const results = [];
  const jobs = [];
  const start = performance.now();
  for (let i = 0; i < requests; i++) {
    const wait = start + i * 1000 / offeredRps - performance.now();
    if (wait > 0) await sleep(wait);
    const fx = picker();
    inFlight++; peakInFlight = Math.max(peakInFlight, inFlight);
    jobs.push(fire(fx, `${runId}-${i}`).then((r) => { inFlight--; results.push({ ...r, fx }); }));
  }
  const windowS = requests / offeredRps;
  await Promise.all(jobs);
  const completionWindowS = Math.max(windowS, (performance.now() - start) / 1000);
  polling = false;
  await poll;
  const after = await scrape();
  const groups = new Map();
  for (const r of results) {
    const k = `${r.fx.kind}|${bucket(r.fx.pages)}`;
    (groups.get(k) ?? groups.set(k, []).get(k)).push(r);
  }
  const rows = [];
  for (const [k, rs] of [...groups].sort()) {
    const [kind, pb] = k.split("|");
    const ok = rs.filter((r) => r.outcome === "ok").map((r) => r.ms).sort((x, y) => x - y);
    const n = rs.length;
    const hq = (stage, q = 0.95) => histQuantile(before, after, `${stage}|${kind}`, q);
    rows.push({
      run_id: runId, input_kind: kind, page_bucket: pb,
      offered_rps: (n / windowS).toFixed(2), completed_rps: (ok.length / completionWindowS).toFixed(2), in_flight: peakInFlight,
      p50_ms: pct(ok, 0.5), p95_ms: pct(ok, 0.95), p99_ms: pct(ok, 0.99),
      queue_p95_ms: hq("queue_wait"), ocr_p95_ms: kind === "ocr" ? hq("extract") : "", model_p95_ms: hq("model"),
      peak_rss_mib: peakRss ? Math.round(peakRss / 2 ** 20) : "", peak_vram_mib: peakVram ? Math.round(peakVram / 2 ** 20) : "",
      rejected_pct: ((100 * rs.filter((r) => r.outcome === "rejected").length) / n).toFixed(1),
      error_pct: ((100 * rs.filter((r) => r.outcome === "error").length) / n).toFixed(1),
    });
  }
  return rows;
}

// ---- main ----
const fixtures = await loadFixtures();
const scanShare = num("scan-share");
const pick = () => {
  const want = Math.random() < scanShare ? "ocr" : "pdf_text";
  const pool = fixtures.filter((f) => f.kind === want);
  const from = pool.length ? pool : fixtures;
  return from[Math.floor(Math.random() * from.length)];
};
const id = o["run-id"] ?? `${o.mode}-${new Date().toISOString().replace(/[-:T]/g, "").slice(0, 14)}`;
const rows = [];
// Warmup always runs first (sequential), then the fixture parity pass, then the measured phases.
for (let i = 0; i < num("warmup-requests"); i++) await fire(pick(), `${id}-warm-${i}`);
if (o.mode === "warmup") rows.push(...(await phase(`${id}`, num("warmup-requests"), 1, pick)));

const failures = [];
if (!o["skip-fixtures"] && o.route === "runs") {
  for (const fx of fixtures.filter((f) => f.expect)) {
    const r = await fire(fx, `${id}-fx-${fx.name}`);
    if (r.outcome !== "ok") failures.push(`${fx.name}: ${r.outcome}`);
    else if (r.status !== fx.expect.status || (r.status === "refused" && fx.expect.code && r.code !== fx.expect.code)) {
      failures.push(`${fx.name}: expected ${fx.expect.status}${fx.expect.code ? `/${fx.expect.code}` : ""}, got ${r.status}${r.code ? `/${r.code}` : ""}`);
    }
  }
}
if (o.mode === "sustained") {
  for (const rps of o.rps.split(",").map(Number)) rows.push(...(await phase(`${id}-r${rps}`, Math.max(1, Math.round(rps * num("duration"))), rps, pick)));
} else if (o.mode === "burst") {
  const n = num("burst-requests"), w = num("burst-window");
  rows.push(...(await phase(`${id}-burst`, n, n / w, pick)));
} else if (o.mode !== "warmup") throw new Error("--mode must be warmup, sustained or burst");

const csv = [COLUMNS.join(","), ...rows.map((r) => COLUMNS.map((c) => r[c]).join(","))].join("\n") + "\n";
if (o.out) await writeFile(o.out, csv); else process.stdout.write(csv);

// ---- promotion gate (sustained rows are the ones judged; a burst is expected to reject) ----
if (o.mode !== "burst") {
  for (const r of rows) {
    const limit = r.input_kind === "ocr" ? num("max-p95-scan-ms") : num("max-p95-text-ms");
    if (r.page_bucket === "1" && r.p95_ms !== "" && r.p95_ms > limit) failures.push(`${r.run_id} ${r.input_kind} p95 ${r.p95_ms} ms > ${limit} ms`);
    if (Number(r.error_pct) > num("max-error-pct")) failures.push(`${r.run_id} ${r.input_kind}/${r.page_bucket} error ${r.error_pct}% > ${o["max-error-pct"]}%`);
    if (Number(r.rejected_pct) > num("max-rejected-pct")) failures.push(`${r.run_id} ${r.input_kind}/${r.page_bucket} rejected ${r.rejected_pct}% > ${o["max-rejected-pct"]}%`);
    if (o["max-rss-mib"] && r.peak_rss_mib !== "" && r.peak_rss_mib > num("max-rss-mib")) failures.push(`${r.run_id} peak RSS ${r.peak_rss_mib} MiB > ${o["max-rss-mib"]} MiB`);
  }
}
if (failures.length) {
  console.error(`GATE FAIL\n- ${failures.join("\n- ")}`);
  process.exit(1);
}
console.error("GATE PASS (fixtures match, thresholds met). OOM restarts are not observable here: check `docker inspect` RestartCount.");
