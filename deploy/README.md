# Deploy Open Books on one host

For separate inference and website hosts, follow the [inference rollout](../docs/INFERENCE_ROLLOUT.md).

Docker Compose runs Caddy, the Next.js website, and the Python engine on the same Linux host. The engine's port is private to the Compose network. The engine image includes the calibrated model and preloads EasyOCR's English weights during the build. The website waits for the engine to report that both are available.

Point the website DNS record at the host and make ports 80 and 443 available to Caddy. With Docker Engine and the Compose plugin installed, run these commands from the repository root:

```sh
export OPENBOOKS_SITE_ADDRESS=books.example.com
docker compose config --quiet
docker compose up -d --build --wait
node deploy/smoke.mjs "https://$OPENBOOKS_SITE_ADDRESS"
```

The smoke test checks health, runs a packaged statement with explicit INR and day-first dates, and verifies its expected transaction fields and model provenance. Pass a path to a PNG or JPEG as the second argument to verify OCR and role inference too. Use a synthetic image when checking a newly deployed instance.

The self-hosted upload route accepts up to 2 GiB of file data per run and allows 1 MiB for multipart framing and fields. The engine writes one temporary copy and removes it after processing. Give the engine temporary volume room for concurrent uploads. A single upload stops if the host approaches its free-space reserve. Text formats retain their 64 MiB parser limit. The Netlify Functions request limit applies to the hosted site, so large uploads require the streaming self-hosted route or another streaming ingress.

### Optional original retention

Keep retention flags off until the deletion worker is running. Apply `web/migrations/004_retained_originals.sql` and provision a private Neon Object Storage bucket. On the upload engine, install the server's `retention` extra and configure `OPENBOOKS_RETENTION_DATABASE_URL`, `OPENBOOKS_STORAGE_ENDPOINT`, `OPENBOOKS_STORAGE_BUCKET`, and the scoped S3 credentials. The database role needs insert, select, and update access to `retained_originals`. Keep these credentials on the VPS.

Install and enable `openbooks-originals-expiry.timer` and its matching service. Verify the service can delete an expired synthetic object and record `deleted_at`, including a retry after a failed delete. Reload `Caddyfile.upload` so only the authenticated authorization response can supply an owner. Then set `OPENBOOKS_RETENTION_ENABLED=1` on the upload engine and the web server, and `NEXT_PUBLIC_OPENBOOKS_RETENTION_ENABLED=1` for the web build. Check both an opted-in synthetic upload and an ordinary upload before release. Neon stores S3 lifecycle configurations without enforcing the rules, so the timer enforces the 30-day expiry.

For a local sandbox, use `OPENBOOKS_SITE_ADDRESS=:80`, `OPENBOOKS_HTTP_BIND=127.0.0.1:3080`, and `OPENBOOKS_HTTPS_BIND=127.0.0.1:3443`. Run with `docker compose -p openbooks-sandbox` and test `http://127.0.0.1:3080`.

Q&A is optional. Set `OPENBOOKS_LLM_API_KEY`, `OPENBOOKS_LLM_MODEL`, and, if needed, `OPENBOOKS_LLM_BASE_URL` on the VPS. The upload, OCR, and model reading routes run without these values.

The public API uses a shared PostgreSQL rate limiter. Apply `web/migrations/001_rate_buckets.sql` to a test branch first and then to the target database using a direct connection. Set `DATABASE_URL` to the pooled Neon connection in the deployment environment. Production requests to limited routes return 503 if the database or migration is unavailable. Keep the web service behind the configured trusted reverse proxy: the limiter uses the last `X-Forwarded-For` address supplied by that proxy (or Netlify's client IP header). Do not expose the web service directly to untrusted clients.

## Developer documentation and search

The Open Books Netlify project serves the landing page at `https://books.openlumeo.com/`, the Fumadocs docs under `/docs/` and the workspace at `/app`. Edit public pages in `web/content/docs/` and add entries to `meta.json` for sidebar navigation. HTML, the sitemap, `/llms.txt`, `/llms-full.txt` and per-page Markdown share the same content. Keep page descriptions specific and examples aligned with released package versions.

In the Neon Auth settings for the branch in the production `NEON_AUTH_BASE_URL`, add `https://books.openlumeo.com` as a trusted origin. Neon checks the request origin for email sign-in and the callback URL for Google sign-in.

Run `pnpm test` from `web/` before pushing to the production branch. The Netlify build runs `deploy/build-public-assets.py` to publish the JSON schemas with the site. To prepare the same files locally, run `python deploy/build-public-assets.py` from the repository root, then run `pnpm build` from `web/`. The asset script needs Python 3.11 or newer.

After publishing, check the homepage, `/app`, `/docs/quickstart`, docs search, `/robots.txt`, `/sitemap.xml`, `/llms.txt`, and the MCP download on the custom domain. Run both terminal examples. Use canonical HTML URLs in the sitemap and let crawlers read the `noindex` directive on the workspace. [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) · [Canonical URL guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)

Apply `web/migrations/002_agent_onboarding.sql` to the website database before deploying the agent setup widget. The web test suite exercises the Setup MCP transport against a disposable PostgreSQL instance. After release, start a setup in the docs and confirm it with an MCP tool call. The confirmation endpoint is dedicated to pairing codes. The full MCP server continues to handle files over its private or local transports.

Submit `/sitemap.xml` once in the verified Google Search Console property. After a release, check the homepage and key docs in URL Inspection and review indexing errors as they appear. Compare query impressions, clicks and landing pages over rolling 28-day periods each week. Prioritise pages for relevant queries such as bank statement CSV to JSON, PDF statement OCR and Stripe settlement reconciliation. Improve pages with incomplete examples, support questions or low click-through rates. Keep page dates tied to substantive content changes. [Google SEO starter guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) · [Search Console performance report](https://support.google.com/webmasters/answer/7576553)

Keep public docs and AI exports reachable through the CDN and bot rules. Check the actual HTML Googlebot receives, including the canonical, content, and internal href links. Treat Markdown exports as an access path for agents and track Google visibility through the HTML pages and Search Console. [Google's guide to AI search visibility](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
