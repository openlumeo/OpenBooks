import { execFileSync } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { FETCH_TIMEOUT_MS, fetchText, parseSitemapEntries } from "./lib.mjs";

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PUBLIC_DIR = path.join(REPO_ROOT, "web", "public");
const ENDPOINT = "https://api.indexnow.org/IndexNow";
const DEFAULT_HOST = "openbooks.lumeo.co.in";
const MAX_URLS_PER_POST = 10000;
const KEY_PATTERN = /^[a-f0-9]{8,128}$/i;
const KEY_FILE_PATTERN = /^([a-f0-9]{8,128})\.txt$/i;
const CONTENT_PREFIXES = ["web/content/", "web/app/"];

function resolveKey(env, publicFiles) {
  const fromEnv = env.INDEXNOW_KEY?.trim();
  if (fromEnv) {
    if (!KEY_PATTERN.test(fromEnv)) {
      throw new Error("INDEXNOW_KEY must be 8 to 128 hex characters");
    }
    return fromEnv;
  }
  const committed = publicFiles.map((file) => file.match(KEY_FILE_PATTERN)?.[1]).filter(Boolean);
  if (committed.length > 1) {
    throw new Error("more than one IndexNow key file in web/public; set INDEXNOW_KEY to choose");
  }
  return committed[0] ?? null;
}

function gitOutput(args) {
  return execFileSync("git", args, { cwd: REPO_ROOT, encoding: "utf8" }).trim();
}

function selectChanged(entries) {
  if (entries.some((entry) => entry.lastmod)) {
    const previousCommitTime = Date.parse(gitOutput(["log", "-1", "--format=%cI", "HEAD~1"]));
    if (Number.isNaN(previousCommitTime)) {
      throw new Error("cannot read the previous commit time");
    }
    return entries.filter((entry) => entry.lastmod && Date.parse(entry.lastmod) >= previousCommitTime);
  }
  const changedFiles = gitOutput(["diff", "--name-only", "HEAD~1", "HEAD"]).split("\n");
  const contentChanged = changedFiles.some((file) => CONTENT_PREFIXES.some((prefix) => file.startsWith(prefix)));
  return contentChanged ? entries : [];
}

async function loadEntries({ sitemapFile, sitemapUrl }) {
  if (sitemapFile) {
    return parseSitemapEntries(readFileSync(sitemapFile, "utf8"));
  }
  const response = await fetchText(sitemapUrl);
  if (response.status !== 200) {
    throw new Error(`sitemap ${sitemapUrl} returned ${response.status}`);
  }
  return parseSitemapEntries(response.body);
}

function chunk(items, size) {
  const batches = [];
  for (let index = 0; index < items.length; index += size) {
    batches.push(items.slice(index, index + size));
  }
  return batches;
}

async function verifyKeyFile(keyLocation, key) {
  const response = await fetchText(keyLocation);
  if (response.status !== 200) {
    throw new Error(`key file ${keyLocation} returned ${response.status}`);
  }
  if (response.body.trim() !== key) {
    throw new Error(`key file ${keyLocation} does not contain the key`);
  }
}

async function submit(payload) {
  const response = await fetch(ENDPOINT, {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(payload),
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  if (response.status !== 200 && response.status !== 202) {
    throw new Error(`IndexNow responded ${response.status}: ${await response.text()}`);
  }
  return response.status;
}

async function main() {
  const { values } = parseArgs({
    options: {
      "dry-run": { type: "boolean", default: false },
      "changed-only": { type: "boolean", default: false },
      "sitemap-file": { type: "string" },
      "sitemap-url": { type: "string" },
      host: { type: "string", default: DEFAULT_HOST },
    },
  });
  const host = values.host;
  const key = resolveKey(process.env, readdirSync(PUBLIC_DIR));
  if (!key && !values["dry-run"]) {
    throw new Error("no key: set INDEXNOW_KEY or commit web/public/<key>.txt");
  }
  const keyLocation = key ? `https://${host}/${key}.txt` : null;

  const entries = await loadEntries({
    sitemapFile: values["sitemap-file"],
    sitemapUrl: values["sitemap-url"] ?? `https://${host}/sitemap.xml`,
  });
  const foreign = entries.find((entry) => new URL(entry.loc).hostname !== host);
  if (foreign) {
    throw new Error(`sitemap URL outside ${host}: ${foreign.loc}`);
  }
  const selected = values["changed-only"] ? selectChanged(entries) : entries;
  const urls = [...new Set(selected.map((entry) => entry.loc))];
  console.log(`${urls.length} of ${entries.length} sitemap URLs selected for ${host}`);
  if (urls.length === 0) {
    console.log("nothing to submit");
    return;
  }

  const batches = chunk(urls, MAX_URLS_PER_POST);
  if (values["dry-run"]) {
    batches.forEach((batch, index) => console.log(`dry run: batch ${index + 1}/${batches.length} has ${batch.length} URLs`));
    console.log(`dry run: no request sent (key location would be ${keyLocation ?? "unset, INDEXNOW_KEY missing"})`);
    return;
  }

  await verifyKeyFile(keyLocation, key);
  for (const [index, batch] of batches.entries()) {
    const status = await submit({ host, key, keyLocation, urlList: batch });
    console.log(`batch ${index + 1}/${batches.length}: ${batch.length} URLs, HTTP ${status}`);
  }
}

main().catch((error) => {
  console.error(`indexnow: ${error.message}`);
  process.exitCode = 1;
});
