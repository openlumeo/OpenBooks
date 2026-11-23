# openbooks

Open Books returns one proven JSON document per file, or a typed refusal, from the command line. A file is released only if its own arithmetic balances.

```bash
npm install -g @lumeo_hq/openbooks   # also installs the Python engine with OCR and model support
openbooks statement.csv --currency INR --opening 1000.00   # same as: openbooks run statement.csv ...
openbooks gateways stripe.csv              # only gateway layouts; anything else is refused
openbooks doctor
```

Commands: `run`, `statements run`, `gateways run`, `tax run`, `doctor`, `install-engine`, `engine-info`. Flags: `--currency --opening --account
--allow-derived-opening --date-order dmy|mdy --no-ocr --no-model --out <dir> --json --python <path> --timeout <ms>`.

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.
PDF and image runs use the model on your machine by default. Pass `--no-model` to skip the cross-check.
The npm install hook fetches `openbooks[scan]` 0.2.x for Python 3.11+, including PyTorch. If your package manager skips the hook or you set `OPENBOOKS_SKIP_PYTHON=1`, run `openbooks install-engine --scan`.
If your system Python refuses global installs, create a `.venv` in your project and run `openbooks install-engine --scan` from that directory.

## Automate a run

~~~sh
openbooks statements run statement.csv --currency INR --opening 1000.00 \
  --date-order dmy --max-document-bytes 67108864 --out ./proofs --json
~~~

`--json` emits a result array on stdout. `--out` also writes the engine documents to hash-named files. Reusing the output directory replaces any result for identical input bytes. Use separate output directories to compare runs with different settings. An oversized proof reports an engine error. For per-file options and streaming decisions, use the [Node.js SDK](https://openbooks.lumeo.co.in/docs/node).

## Formats and limits

- Bank statements: CSV, OFX, MT940 and text-layer PDFs. Scans and images need OCR (installed by the Python engine with `[scan]`).
- Payment gateway exports and tax documents are read by the same engine; PayPal, Wise and the tax layouts are experimental.
- Limits: 2 GB per document. Text formats (`.csv`, `.ofx`, `.qfx`, `.sta`, `.mt940`, `.txt`, `.xml`) are capped at 64 MB. `.xml` is accepted for CAMT.053 statements (`camt053.v1`).
- Everything is tested on synthetic fixtures only. Pre-release.

## Links

- Developer docs: https://openbooks.lumeo.co.in/docs
- MCP server for AI agents: https://openbooks.lumeo.co.in/docs/mcp (npm package `@lumeo_hq/openbooks-mcp`)
- Source: https://github.com/Sagexd08/OpenBooks

[CLI command reference and troubleshooting](https://openbooks.lumeo.co.in/docs/cli)
