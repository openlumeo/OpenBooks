# openbooks

Financial documents in, **one proven JSON document per file out, or a typed refusal**. Never guessed. Never partially released.

Open Books reads bank statements, payment-gateway exports and tax documents into a canonical `openbooks.v1` record. A file is
released only if its numbers prove themselves (balances tie, totals match, and at least one check is independent evidence from the
document itself); otherwise it is refused with a typed code. Every released field keeps its evidence: page, bounding box, row,
raw text and extraction method. Money is `Decimal` end to end and nothing is rounded silently.

This is the meta package: it installs the whole open stack and keeps `import openbooks.pipeline` working.

```bash
pip install openbooks            # core, statements (with PDF), gateways, tax, doctor
pip install "openbooks[scan]"    # adds OCR for scans and the typed heads (EasyOCR, PyTorch, Pillow)
openbooks doctor
openbooks run statement.csv --currency INR --opening 1000.00 --out out
```

| Package | Reads |
|---|---|
| `openbooks-core` | the contract, normalisation, balance gates, layout registry, CLI |
| `openbooks-statements` | bank CSV, OFX, MT940, PDFs, scans |
| `openbooks-gateways` | Stripe, Razorpay, PayPal, Wise |
| `openbooks-tax` | Form 26AS, AIS, FIRA, Form 1099-B, trial balance |
| `openbooks-doctor` | installation, provider and model-integrity checks |

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.

> **Status: 0.1, pre-release.** Every layout has been exercised on synthetic fixtures only, not on real exports, and PayPal, Wise
> and all the tax layouts are experimental. Do not rely on it for real filings.

Licence: Apache-2.0.
