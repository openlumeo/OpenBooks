# Open Books harness eval

Deterministic install self-check for the Open Books MCP server. It starts the server over stdio, makes the checks below with no LLM involved, and writes a machine-readable report. It is the proof that an install works.

## Run

```bash
python harness/eval/selfcheck.py
```

The default server command is `npx -y @lumeo_hq/openbooks-mcp`. Point it at a local build with `--command`:

```bash
python harness/eval/selfcheck.py --command "node packages/js/mcp/dist/cli.js"
```

Options:

| Flag | Meaning |
|---|---|
| `--command` | Command that starts the MCP server over stdio. Default `npx -y @lumeo_hq/openbooks-mcp`. |
| `--report` | JSON report path. Default `harness/eval/report.json`. |
| `--repeat N` | Run the suite N times. Reports pass@1 and pass^N. |
| `--root DIR` | Directory passed as `--root` to the scoped server for task T9. Default is a temporary directory. |

The only Python dependency is the `mcp` client package. The script exits 0 when every check passes, 1 when any check fails, and 2 when the server cannot start.

Harness command: `harness-selfcheck` (`python harness/eval/selfcheck.py`).

## What it proves

- The server speaks MCP over stdio and lists its tools `search` and `execute`, each with a title, a read-only hint and an output schema.
- Resources and prompts are listed.
- `doctor` reports `healthy: true` and a released sample.
- Verification outcomes match the refusal contract: releases, typed refusals, input limits, path confinement and the response budget.

## The 10 tasks

Surface checks S1 to S4 run first: tools, resources, prompts, and doctor.

| ID | Task | Expected |
|---|---|---|
| T1 | Balanced statement with opening 1000.00 | `ok` (released) |
| T2 | Same statement without opening | `PARSE_ERROR` |
| T3 | Tampered closing balance, opening 1000.00, via `process_upload` base64 | `BALANCE_MISMATCH` |
| T4 | Balanced CAMT.053 upload | `ok` (released) |
| T5 | CAMT.053 with a DOCTYPE declaration | `PARSE_ERROR` |
| T6 | Upload with unsupported extension | `UNSUPPORTED_INPUT` |
| T7 | Upload over 1 MiB decoded | `INPUT_LIMIT` |
| T8 | `records` on a refused document | `DOCUMENT_REFUSED` |
| T9 | `process_file` with `../` and an absolute path under `--root` | `INVALID_PATH` for both |
| T10 | 200-row upload: `document` step and a 10-row `records` page | response is valid JSON under 48 KiB, document is `RESPONSE_LIMIT` |

Fixtures are in `harness/eval/fixtures/`.

## Reliability metrics

- pass@1: share of checks that pass in the first run.
- pass^k: share of checks that pass in all k runs. Use `--repeat 3` or more in CI.

## CI

`.github/workflows/harness.yml` runs on changes under `harness/**`, `packages/js/mcp/**` and `scripts/harness/**`. It:

1. Installs Node 20 and Python 3.12.
2. Builds `packages/js` with the pnpm workspace (`pnpm --dir packages/js install --frozen-lockfile`, then `pnpm --dir packages/js build`).
3. Runs `harness/eval/selfcheck.py --command "node packages/js/mcp/dist/cli.js" --repeat 3`.
4. Builds the kit with `scripts/harness/build_kit.py` and uploads the zip and its `.sha256` file as an artifact.

Any failing check fails the job.
