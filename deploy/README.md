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

For a local sandbox, use `OPENBOOKS_SITE_ADDRESS=:80`, `OPENBOOKS_HTTP_BIND=127.0.0.1:3080`, and `OPENBOOKS_HTTPS_BIND=127.0.0.1:3443`. Run with `docker compose -p openbooks-sandbox` and test `http://127.0.0.1:3080`.

Q&A is optional. Set `OPENBOOKS_LLM_API_KEY`, `OPENBOOKS_LLM_MODEL`, and, if needed, `OPENBOOKS_LLM_BASE_URL` on the VPS. The upload, OCR, and model reading routes run without these values.

The public API uses a shared PostgreSQL rate limiter. Apply `web/migrations/001_rate_buckets.sql` to a test branch first and then to the target database using a direct connection. Set `DATABASE_URL` to the pooled Neon connection in the deployment environment. Production requests to limited routes return 503 if the database or migration is unavailable. Keep the web service behind the configured trusted reverse proxy: the limiter uses the last `X-Forwarded-For` address supplied by that proxy (or Netlify's client IP header). Do not expose the web service directly to untrusted clients.

## Developer documentation and search

The Open Books Netlify project serves the landing page at `https://openbooks.openlumeo.com/`, the Fumadocs docs under `/docs/` and the workspace at `/app`. Edit public pages in `web/content/docs/` and add entries to `meta.json` for sidebar navigation. HTML, the sitemap, `/llms.txt`, `/llms-full.txt` and per-page Markdown share the same content. Keep page descriptions specific and examples aligned with released package versions.

Run `pnpm test` from `web/` before pushing to the production branch. The Netlify build runs `deploy/build-public-assets.py` to publish the JSON schemas with the site. To prepare the same files locally, run `python deploy/build-public-assets.py` from the repository root, then run `pnpm build` from `web/`. The asset script needs Python 3.11 or newer.

After publishing, check the homepage, `/app`, `/docs/quickstart`, docs search, `/robots.txt`, `/sitemap.xml`, `/llms.txt`, and the MCP download on the custom domain. Run both terminal examples. Use canonical HTML URLs in the sitemap and let crawlers read the `noindex` directive on the workspace. [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) · [Canonical URL guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)

Apply `web/migrations/002_agent_onboarding.sql` to the website database before deploying the agent setup widget. The web test suite exercises the Setup MCP transport against a disposable PostgreSQL instance. After release, start a setup in the docs and confirm it with an MCP tool call. The confirmation endpoint is dedicated to pairing codes. The full MCP server continues to handle files over its private or local transports.

Submit `/sitemap.xml` once in the verified Google Search Console property. After a release, check the homepage and key docs in URL Inspection and review indexing errors as they appear. Compare query impressions, clicks and landing pages over rolling 28-day periods each week. Prioritise pages for relevant queries such as bank statement CSV to JSON, PDF statement OCR and Stripe settlement reconciliation. Improve pages with incomplete examples, support questions or low click-through rates. Keep page dates tied to substantive content changes. [Google SEO starter guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) · [Search Console performance report](https://support.google.com/webmasters/answer/7576553)

Keep public docs and AI exports reachable through the CDN and bot rules. Check the actual HTML Googlebot receives, including the canonical, content, and internal href links. Treat Markdown exports as an access path for agents and track Google visibility through the HTML pages and Search Console. [Google's guide to AI search visibility](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
