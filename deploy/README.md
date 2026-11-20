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
