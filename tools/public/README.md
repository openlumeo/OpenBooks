# Open Books

Financial documents in, **one proven JSON document per file out, or a typed refusal**. Never guessed. Never partially released.

Open Books reads bank statements, payment-gateway exports and tax documents into a canonical `openbooks.v1` record. A file is
released only if its numbers prove themselves (balances tie, totals match, and at least one check is independent evidence from the
document itself); otherwise it is refused with a typed code. Every released field keeps its evidence: page, bounding box, row,
raw text and extraction method. Money is `Decimal` end to end and nothing is rounded silently.

> **Status: pre-release. Nothing is published to PyPI or npm yet.** Every layout has been exercised on synthetic fixtures only,
> not on real exports, and PayPal, Wise and all the tax layouts are experimental. Do not rely on it for real filings.

## Packages

| Python | Reads | Install extras |
|---|---|---|
| `openbooks-core` | the contract, normalisation, balance gates, layout registry, CLI | `[xlsx]` |
| `openbooks-statements` | bank CSV, OFX, MT940 (pure Python) | `[pdf]` PDFs (PyMuPDF), `[scan]` OCR and the typed heads |
| `openbooks-gateways` | Stripe, Razorpay, PayPal, Wise | |
| `openbooks-tax` | Form 26AS, AIS, FIRA, Form 1099-B, trial balance | |
| `openbooks-doctor` | `openbooks doctor`: installation, provider and model-integrity checks | |
| `openbooks` | meta package: installs the above | `[scan]` |

npm: `@openbooks/core`, `@openbooks/statements`, `@openbooks/gateways`, `@openbooks/tax`, `@openbooks/doctor` and the `openbooks`
CLI are typed wrappers that run the Python engine. They parse nothing themselves.

A package that is not installed never causes a guess: a file that looks like a known layout whose package is missing is refused,
with the name of the package to install.

## From source

```bash
pip install -e packages/py/openbooks-core -e packages/py/openbooks-gateways -e packages/py/openbooks-tax \
            -e "packages/py/openbooks-statements[pdf]" -e packages/py/openbooks-doctor -e packages/py/openbooks
python -m openbooks_core run statement.csv --currency INR --opening 1000.00 --machine
python -m openbooks_core doctor
```

```ts
import { runFile } from "@openbooks/core";
const r = await runFile("statement.csv", { currency: "INR", opening: "1000.00" });
if (r.kind === "released") console.log(r.document.data.transactions[0]?.amount?.amount); // a string, never a float
else console.log(r.code, r.message); // a refusal is a value, not an exception
```

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.

## Licence

See `LICENSE`. Some optional dependencies have their own terms: PyMuPDF (the `[pdf]` extra) is AGPL-3.0 or commercial, and
EasyOCR pulls in `python-bidi` (LGPL). See `THIRD_PARTY.md`.
