<p align="center">
  <img src="https://books.openlumeo.com/brand/mark-black.png" alt="Open Books" width="96" height="102">
</p>

# @lumeo_hq/openbooks

[![Openbooks MCP server](https://mcprush.com/badge/openbooks-mcp/card.svg)](https://mcprush.com/to/openbooks-mcp?ref=badge)

Open Books returns one proven JSON document per file, or a typed refusal, from the command line, from Node.js, or through an MCP server for AI agents. A file is released only if its own arithmetic balances.

One npm package ships everything: the `openbooks` CLI, the `openbooks-mcp` server, and library subpath modules.

## Install

```bash
npm install -g @lumeo_hq/openbooks
```

Requires Node.js 20 or newer and Python 3.11 or newer for the engine. The install hook provisions the Python engine (with OCR and model support). If your package manager skips the hook or you set `OPENBOOKS_SKIP_PYTHON=1`, run:

```bash
npx -y @lumeo_hq/openbooks install-engine --scan
```

If your system Python refuses global installs, create a `.venv` in your project and run `openbooks install-engine --scan` from that directory.

## CLI usage

```bash
openbooks statement.csv --currency INR --opening 1000.00   # same as: openbooks run statement.csv ...
openbooks gateways stripe.csv              # only gateway layouts; anything else is refused
openbooks doctor
```

Commands: `run`, `statements run`, `gateways run`, `tax run`, `doctor`, `install-engine`, `engine-info`. Flags: `--currency --opening --account --allow-derived-opening --date-order dmy|mdy --no-ocr --no-model --out <dir> --json --python <path> --timeout <ms>`.

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.

PDF and image runs use the model on your machine by default. Pass `--no-model` to skip the cross-check.

### Automate a run

~~~sh
openbooks statements run statement.csv --currency INR --opening 1000.00 \
  --date-order dmy --max-document-bytes 67108864 --out ./proofs --json
~~~

`--json` emits a result array on stdout. `--out` also writes the engine documents to hash-named files. Reusing the output directory replaces any result for identical input bytes. Use separate output directories to compare runs with different settings. An oversized proof reports an engine error.

## Library usage

The package exposes one subpath module per area. Import only what you need:

```js
import { runFile, runFiles, runJobs } from "@lumeo_hq/openbooks/statements";
import { runDoctor } from "@lumeo_hq/openbooks/doctor";

const result = await runFile("statement.csv", { currency: "INR", opening: "1000.00" });
const report = await runDoctor();
```

`statements`, `gateways` and `tax` each export `runFile`, `runFiles` and `runJobs`, restricted to their own layouts. `doctor` exports `runDoctor`. `core` holds the shared engine runner, discovery and schema types.

| Subpath | Area |
| --- | --- |
| `@lumeo_hq/openbooks/core` | Engine discovery, process runner, schema types and validation |
| `@lumeo_hq/openbooks/statements` | Bank statement runs |
| `@lumeo_hq/openbooks/gateways` | Payment gateway exports |
| `@lumeo_hq/openbooks/tax` | Tax documents |
| `@lumeo_hq/openbooks/doctor` | Environment and engine diagnostics |
| `@lumeo_hq/openbooks/mcp` | MCP server components |

For per-file options and streaming decisions, use the [Node.js SDK](https://books.openlumeo.com/docs/node).

## MCP server for AI agents

The `openbooks-mcp` bin runs the Model Context Protocol server on stdio:

```bash
npx -y -p @lumeo_hq/openbooks openbooks-mcp
```

See [MCP.md](./MCP.md) for client setup (Claude Code, Codex, Claude Desktop, Cursor, Cline, Gemini CLI), tools, operations, `--root` folder access, HTTP mode and troubleshooting.

## Formats and limits

- Bank statements: CSV, OFX, MT940 and text-layer PDFs. Scans and images need OCR (installed by the Python engine with `[scan]`).
- Payment gateway exports and tax documents are read by the same engine; PayPal, Wise and the tax layouts are experimental.
- Limits: 2 GB per document. Text formats (`.csv`, `.ofx`, `.qfx`, `.sta`, `.mt940`, `.txt`, `.xml`) are capped at 64 MB. `.xml` is accepted for CAMT.053 statements (`camt053.v1`).
- Everything is tested on synthetic fixtures only. Pre-release.

## Links

- Developer docs: https://books.openlumeo.com/docs
- MCP server guide: [MCP.md](./MCP.md) and https://books.openlumeo.com/docs/mcp
- Source: https://github.com/Sagexd08/OpenBooks
- [CLI command reference and troubleshooting](https://books.openlumeo.com/docs/cli)

Exit-code and refusal details: https://books.openlumeo.com/docs/refusals
