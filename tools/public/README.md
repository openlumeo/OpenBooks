# Open Books

Financial documents in, **one proven JSON document per file out, or a typed refusal**. Never guessed. Never partially released.

Open Books reads bank statements, payment-gateway exports and tax documents into a canonical `openbooks.v1` record. A file is
released only if its numbers prove themselves (balances tie, totals match, and at least one check is independent evidence from the
document itself); otherwise it is refused with a typed code. Every released field keeps its evidence: page, bounding box, row,
raw text and extraction method. Money is `Decimal` end to end and nothing is rounded silently.

> **Status: pre-release. Nothing is published to PyPI or npm yet.** Every layout has been exercised on synthetic fixtures only,
> not on real exports, and PayPal, Wise and all the tax layouts are experimental. Do not rely on it for real filings.

## Packages

One Python package, `openbooks` (`pip install openbooks`; add `[scan]` for OCR and the typed heads):

| Module | Reads |
|---|---|
| `openbooks.core` | the contract, normalisation, balance gates, layout registry, CLI |
| `openbooks.statements` | bank CSV, OFX, MT940, PDFs with a text layer; scans with `[scan]` |
| `openbooks.gateways` | Stripe, Razorpay, PayPal, Wise |
| `openbooks.tax` | Form 26AS, AIS, FIRA, Form 1099-B, trial balance |
| `openbooks.doctor` | `openbooks doctor`: installation, provider and model-integrity checks |

npm: `@lumeo_hq/openbooks` (subpath modules `/core`, `/statements`, `/gateways`, `/tax`, `/doctor`, `/mcp`; commands `openbooks` and `openbooks-mcp`) is a typed wrapper that runs the Python engine. It parses nothing itself.

A missing provider never causes a guess: a file that looks like a known layout whose provider is not registered is refused
with a typed code.

## From source

```bash
pip install -e packages/py/openbooks
python -m openbooks run statement.csv --currency INR --opening 1000.00 --machine
python -m openbooks doctor
```

```ts
import { runFile } from "@lumeo_hq/openbooks/core";
const r = await runFile("statement.csv", { currency: "INR", opening: "1000.00" });
if (r.kind === "released") console.log(r.document.data.transactions[0]?.amount?.amount); // a string, never a float
else console.log(r.code, r.message); // a refusal is a value, not an exception
```

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.

## Licence

Apache License 2.0; see `LICENSE` and `NOTICE`. Dependencies keep their own licences (all permissive except `python-bidi`, LGPL, pulled in by
EasyOCR under the optional `[scan]` extra); see `THIRD_PARTY.md`.
