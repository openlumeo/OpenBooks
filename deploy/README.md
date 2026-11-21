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

The Open Books Netlify project serves the workspace at `https://openbooks.lumeo.co.in/` and Fumadocs at `/docs`. Edit public pages in `web/content/docs/` and add new pages to `meta.json` to place them in the sidebar. The sitemap is generated from the content collection. Keep descriptions specific to the question each page answers. Link related guides with descriptive text and keep examples aligned with the published package versions.

Before publishing, run `pnpm build` and `pnpm test` from `web/`. For the linked Netlify project, publish the website with `netlify deploy --prod --context production` from `web/`. After publication, check the homepage, `/docs/quickstart`, `/api/search?query=opening`, `/robots.txt` and `/sitemap.xml` on the custom domain. Run both terminal examples and verify their refusal and release. Canonical tags and sitemap entries should use the custom domain. Keep internal API paths out of the sitemap. [Google sitemap guidance](https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap) · [Canonical URL guidance](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)

Submit `/sitemap.xml` once in the verified Google Search Console property. After a release, check the homepage and key docs in URL Inspection and review indexing errors as they appear. Compare query impressions, clicks and landing pages over rolling 28-day periods each week. Prioritise pages for relevant queries such as bank statement CSV to JSON, PDF statement OCR and Stripe settlement reconciliation. Improve pages with incomplete examples, support questions or low click-through rates. Keep page dates tied to substantive content changes. [Google SEO starter guide](https://developers.google.com/search/docs/fundamentals/seo-starter-guide) · [Search Console performance report](https://support.google.com/webmasters/answer/7576553)
