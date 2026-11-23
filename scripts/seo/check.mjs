import { readFile } from "node:fs/promises";
import path from "node:path";
import { parseArgs } from "node:util";
import { decodeEntities, fetchText, parseSitemapEntries } from "./lib.mjs";

const DEFAULT_BASE = "http://localhost:3000";
const AI_BOTS = ["OAI-SearchBot", "Claude-SearchBot", "PerplexityBot"];
const TITLE_MAX_EXCLUSIVE = 60;
const DESCRIPTION_MIN = 120;
const DESCRIPTION_MAX = 160;
const HARD = "hard";
const SOFT = "soft";

function describeStatus(response) {
  return response.error ? `status ${response.status}: ${response.error}` : `status ${response.status}`;
}

function parseAttributes(tag) {
  return Object.fromEntries(
    [...tag.matchAll(/([\w:-]+)\s*=\s*"([^"]*)"/g)].map(([, name, value]) => [name.toLowerCase(), value]),
  );
}

function metaContent(html, attribute, name) {
  for (const [tag] of html.matchAll(/<meta\b[^>]*>/gi)) {
    const attributes = parseAttributes(tag);
    if (attributes[attribute] === name) {
      return decodeEntities(attributes.content ?? "");
    }
  }
  return null;
}

function jsonLdProblems(blocks) {
  if (blocks.length === 0) {
    return ["no JSON-LD block"];
  }
  const problems = [];
  for (const raw of blocks) {
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch (error) {
      problems.push(`invalid JSON: ${error.message}`);
      continue;
    }
    for (const item of Array.isArray(parsed) ? parsed : [parsed]) {
      if (!item || typeof item !== "object" || !("@context" in item) || !("@type" in item)) {
        problems.push("block lacks @context or @type");
      }
    }
  }
  return problems;
}

function parseRobots(text) {
  const groups = [];
  const sitemaps = [];
  let current = null;
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.replace(/#.*/, "").trim();
    const separator = line.indexOf(":");
    if (separator < 0) {
      continue;
    }
    const field = line.slice(0, separator).trim().toLowerCase();
    const value = line.slice(separator + 1).trim();
    if (field === "sitemap") {
      sitemaps.push(value);
    } else if (field === "user-agent") {
      if (!current || current.hasRules) {
        current = { agents: [], disallow: [], hasRules: false };
        groups.push(current);
      }
      current.agents.push(value.toLowerCase());
    } else if (current && (field === "allow" || field === "disallow")) {
      current.hasRules = true;
      if (field === "disallow") {
        current.disallow.push(value);
      }
    }
  }
  return { groups, sitemaps };
}

function isBlocked(groups, bot) {
  const lower = bot.toLowerCase();
  const group = groups.find((candidate) => candidate.agents.includes(lower))
    ?? groups.find((candidate) => candidate.agents.includes("*"));
  return group ? group.disallow.includes("/") : false;
}

function createHttpLoader(base) {
  return async (urlPath) => {
    try {
      return await fetchText(new URL(urlPath, base));
    } catch (error) {
      return { status: 0, error: error.message, body: "", headers: new Headers() };
    }
  };
}

function createDirLoader(dir) {
  return async (urlPath) => {
    const relative = decodeURIComponent(urlPath).replace(/^\/+|\/+$/g, "");
    const candidates = relative === ""
      ? ["index.html"]
      : [relative, path.join(relative, "index.html"), `${relative}.html`];
    for (const candidate of candidates) {
      try {
        return { status: 200, headers: new Headers(), body: await readFile(path.join(dir, candidate), "utf8") };
      } catch (error) {
        if (error.code !== "ENOENT" && error.code !== "EISDIR") {
          throw error;
        }
      }
    }
    return { status: 404, headers: new Headers(), body: "" };
  };
}

async function checkRobots(load, record) {
  const robots = await load("/robots.txt");
  record("/robots.txt", "status 200", robots.status === 200, describeStatus(robots));
  if (robots.status !== 200) {
    return;
  }
  const { groups, sitemaps } = parseRobots(robots.body);
  record(
    "/robots.txt",
    "lists sitemap.xml",
    sitemaps.some((sitemap) => sitemap.endsWith("/sitemap.xml")),
    sitemaps.join(", ") || "no Sitemap line",
  );
  for (const bot of AI_BOTS) {
    record("/robots.txt", `allows ${bot}`, !isBlocked(groups, bot), isBlocked(groups, bot) ? "blocked" : "allowed");
  }
}

async function checkPage(load, loc, record) {
  const page = await load(new URL(loc).pathname);
  record(loc, "status 200", page.status === 200, describeStatus(page));
  if (page.status !== 200) {
    return;
  }
  const html = page.body;

  const canonicals = [...html.matchAll(/<link\b[^>]*>/gi)]
    .map(([tag]) => parseAttributes(tag))
    .filter((link) => (link.rel ?? "").split(/\s+/).includes("canonical"));
  record(
    loc,
    "one canonical equals URL",
    canonicals.length === 1 && new URL(canonicals[0].href).href === new URL(loc).href,
    canonicals.map((link) => link.href).join(", ") || "none",
  );

  const robotsMeta = metaContent(html, "name", "robots") ?? "";
  const robotsHeader = page.headers.get("x-robots-tag") ?? "";
  record(loc, "not noindex", !/noindex/i.test(`${robotsMeta} ${robotsHeader}`), robotsMeta || robotsHeader || "none");

  const h1Count = (html.match(/<h1\b/gi) ?? []).length;
  record(loc, "exactly one h1", h1Count === 1, `${h1Count} h1`);

  const titleMatch = html.match(/<title[^>]*>([\s\S]*?)<\/title>/i);
  const title = titleMatch ? decodeEntities(titleMatch[1].trim()) : "";
  record(
    loc,
    `title under ${TITLE_MAX_EXCLUSIVE} chars`,
    title.length > 0 && title.length < TITLE_MAX_EXCLUSIVE,
    `${title.length} chars`,
    SOFT,
  );

  const description = metaContent(html, "name", "description") ?? "";
  record(
    loc,
    `description ${DESCRIPTION_MIN}-${DESCRIPTION_MAX} chars`,
    description.length >= DESCRIPTION_MIN && description.length <= DESCRIPTION_MAX,
    `${description.length} chars`,
    SOFT,
  );

  record(loc, "og:image", Boolean(metaContent(html, "property", "og:image")), "", SOFT);
  record(loc, "twitter:image", Boolean(metaContent(html, "name", "twitter:image")), "", SOFT);

  const blocks = [...html.matchAll(/<script\b[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi)]
    .map(([, body]) => body);
  const problems = jsonLdProblems(blocks);
  record(loc, "JSON-LD valid", problems.length === 0, problems.join("; ") || `${blocks.length} block(s)`);
}

function printResults(results) {
  const rows = results.filter((result) => result.status !== "PASS");
  if (rows.length === 0) {
    return;
  }
  const headers = ["result", "url", "check", "detail"];
  const cells = rows.map((row) => [row.status, row.url, row.check, row.detail]);
  const widths = headers.map((header, column) =>
    Math.max(header.length, ...cells.map((row) => row[column].length)),
  );
  const format = (row) => row.map((cell, column) => cell.padEnd(widths[column])).join("  ");
  console.log(format(headers));
  console.log(widths.map((width) => "-".repeat(width)).join("  "));
  for (const row of cells) {
    console.log(format(row));
  }
}

async function main() {
  const { values } = parseArgs({
    options: {
      base: { type: "string" },
      dir: { type: "string" },
      soft: { type: "boolean", default: false },
    },
  });
  if (values.base && values.dir) {
    throw new Error("use --base or --dir, not both");
  }
  const load = values.dir
    ? createDirLoader(values.dir)
    : createHttpLoader(new URL(values.base ?? DEFAULT_BASE));

  const results = [];
  const record = (url, check, passed, detail = "", severity = HARD) => {
    let status = "PASS";
    if (!passed) {
      status = severity === SOFT && values.soft ? "WARN" : "FAIL";
    }
    results.push({ url, check, status, detail });
  };

  const sitemap = await load("/sitemap.xml");
  record("/sitemap.xml", "status 200", sitemap.status === 200, describeStatus(sitemap));
  let entries = [];
  if (sitemap.status === 200) {
    try {
      entries = parseSitemapEntries(sitemap.body);
    } catch (error) {
      record("/sitemap.xml", "parses", false, error.message);
    }
  }
  record("/sitemap.xml", "has URLs", entries.length > 0, `${entries.length} URLs`);

  const llms = await load("/llms.txt");
  record("/llms.txt", "status 200 and non-empty", llms.status === 200 && llms.body.trim().length > 0, describeStatus(llms));

  await checkRobots(load, record);
  for (const entry of entries) {
    await checkPage(load, entry.loc, record);
  }

  printResults(results);
  const failures = results.filter((result) => result.status === "FAIL").length;
  const warnings = results.filter((result) => result.status === "WARN").length;
  const passed = results.length - failures - warnings;
  console.log(`${passed} passed, ${warnings} warnings, ${failures} failed (${entries.length} pages)`);
  process.exitCode = failures > 0 ? 1 : 0;
}

main().catch((error) => {
  console.error(`seo check: ${error.message}`);
  process.exitCode = 2;
});
