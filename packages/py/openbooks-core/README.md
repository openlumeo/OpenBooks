# openbooks-core

The core of Open Books: financial documents in, **one proven JSON document per file out, or a typed refusal**. Never guessed.
Never partially released.

This package owns the `openbooks.v1` contract (JSON Schema), Decimal and date normalisation, field evidence, the input guard,
the balance gates, the layout registry and the `openbooks` CLI. It contains no parsers: install the providers for the documents
you read.

| Package | Reads |
|---|---|
| `openbooks-statements` | bank CSV, OFX, MT940; `[pdf]` PDFs; `[scan]` scans (OCR) and the typed heads |
| `openbooks-gateways` | Stripe, Razorpay, PayPal, Wise |
| `openbooks-tax` | Form 26AS, AIS, FIRA, Form 1099-B, trial balance |
| `openbooks-doctor` | `openbooks doctor`: installation, provider and model-integrity checks |
| `openbooks` | all of the above |

```bash
pip install openbooks-core                            # only jsonschema is installed
python -m openbooks_core engine-info                  # version, contract version, installed layouts (JSON)
python -m openbooks_core run file.csv --machine       # JSON lines on stdout
```

With no provider installed every known layout is refused with the name of the package to install; nothing is ever released by
guesswork. A file that looks like a known layout whose provider is missing is refused, never passed to a looser parser.

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.

> **Status: 0.1, pre-release.** Every layout has been exercised on synthetic fixtures only, not on real exports. Do not rely on it
> for real filings.

Licence: Apache-2.0.
