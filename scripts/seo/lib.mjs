export const FETCH_TIMEOUT_MS = 20000;

const ENTITIES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", "#39": "'" };

export function decodeEntities(text) {
  return text.replace(/&(amp|lt|gt|quot|apos|#39);/g, (_, name) => ENTITIES[name]);
}

export function parseSitemapEntries(xml) {
  return [...xml.matchAll(/<url>([\s\S]*?)<\/url>/g)].map(([, block]) => {
    const loc = block.match(/<loc>\s*([^<\s]+)\s*<\/loc>/)?.[1];
    if (!loc) {
      throw new Error("sitemap <url> entry without <loc>");
    }
    return {
      loc: decodeEntities(loc),
      lastmod: block.match(/<lastmod>\s*([^<\s]+)\s*<\/lastmod>/)?.[1] ?? null,
    };
  });
}

export async function fetchText(url) {
  const response = await fetch(url, {
    redirect: "manual",
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
  return { status: response.status, headers: response.headers, body: await response.text() };
}
