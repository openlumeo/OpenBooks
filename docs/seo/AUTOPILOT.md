# SEO autopilot

What runs without a human, how to run it locally, and what stays manual.

## What it does

- `scripts/seo/check.mjs` fetches `/sitemap.xml`, `/robots.txt`, `/llms.txt` and every sitemap URL. It asserts status 200, one canonical equal to the URL, title under 60 characters, description 120 to 160 characters, exactly one h1, og:image and twitter:image, valid JSON-LD with `@context` and `@type`, no noindex, a robots.txt Sitemap line, and that OAI-SearchBot, Claude-SearchBot and PerplexityBot are not blocked. Failures exit 1.
- `scripts/seo/indexnow.mjs` reads sitemap URLs and POSTs them to `https://api.indexnow.org/IndexNow` for host `openbooks.openlumeo.com`, in batches of 10,000 or fewer. It checks that the key file is served before posting.
- `.github/workflows/seo.yml` runs on push to main, weekly, and on demand. It builds, starts the app on port 3000, and runs `check.mjs`. On push to main it runs `indexnow.mjs --changed-only` only when the `INDEXNOW_KEY` secret or a committed key file exists.

Soft checks (title length, description length, og and twitter images) fail by default. Pass `--soft` to report them as warnings.

## Keys

The IndexNow key is public by design. It lives in `web/public/<key>.txt` (the file contains only the key), so the host can verify ownership. The `INDEXNOW_KEY` secret, when set, takes precedence and must match that file. Only one key file may exist.

## Run locally

```sh
cd web
pnpm build
pnpm start            # in a second shell, or use pnpm dev
pnpm seo:check        # against http://localhost:3000
node ../scripts/seo/check.mjs --dir web/out --soft   # static output directory
```

IndexNow:

```sh
cd web
pnpm seo:indexnow -- --dry-run --changed-only
node ../scripts/seo/indexnow.mjs --dry-run --sitemap-file ./sitemap.xml   # offline
INDEXNOW_KEY=<key> pnpm seo:indexnow -- --changed-only                     # posts for real
```

`--dry-run` sends no request. With `--sitemap-file` it needs no network.

## Why Google gets no ping

Google retired the sitemap ping endpoint in 2023, and the Indexing API is limited to JobPosting and BroadcastEvent. Neither is called here. Google finds changes through the sitemap (keep `lastmod` honest) and internal links. IndexNow covers Bing, Yandex, Seznam and Naver only.

## Manual steps (cannot be automated)

1. Search Console: verify the Domain property (DNS TXT) and submit `sitemap.xml`.
2. Bing Webmaster Tools: import from Search Console or verify manually, then check Reports and Data, IndexNow.
3. Set the `INDEXNOW_KEY` repository secret if you want the key out of the repo. Otherwise the committed key file is used.
4. MCP Registry: publish with `mcp-publisher` (the npm package carries `mcpName` in package.json).
5. Post launches (Show HN, dev.to, awesome lists, registries). Drafts only; a human posts them.

## Known gaps

- IndexNow verifies the key file on production, so the deploy must be live before the indexnow job runs. A failed key check fails the job; rerun it after deploy.
- `web/app/robots.ts` does not name Claude-SearchBot. It is allowed through the wildcard rule, and the check passes that way.
- The check uses regex HTML parsing. It is built for this site's markup, not for arbitrary HTML.
