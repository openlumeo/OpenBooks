# openbooks

Open Books returns **one proven JSON document per file, or a typed refusal** for bank statements, payment-gateway exports and tax documents. Never guessed. Never partially released.

Open Books reads bank statements, payment-gateway exports and tax documents into a canonical `openbooks.v1` record. A file is
released only if its numbers prove themselves (balances tie, totals match, and at least one check is independent evidence from the
document itself); otherwise it is refused with a typed code. Every released field keeps its evidence: page, bounding box, row,
raw text and extraction method. Money is `Decimal` end to end and nothing is rounded silently.

```bash
pip install openbooks            # every layout, PDFs with a text layer, doctor
pip install "openbooks[scan]"    # adds OCR for scans and the typed heads (EasyOCR, PyTorch, Pillow)
openbooks doctor
openbooks run statement.csv --currency INR --opening 1000.00 --out out
```

```python
from decimal import Decimal
from pathlib import Path

from openbooks import Params, process

doc = process(Path("statement.csv"), Params(currency="INR", opening=Decimal("1000.00")))
print(doc["status"], doc.get("error"))   # a refusal is a value, not an exception
```

Everything is in this one package:

| Module | Reads |
|---|---|
| `openbooks.core` | the contract, normalisation, balance gates, layout registry, CLI |
| `openbooks.statements` | bank CSV, OFX, MT940, PDFs; scans with `[scan]` |
| `openbooks.gateways` | Stripe, Razorpay, PayPal, Wise |
| `openbooks.tax` | Form 26AS, AIS, FIRA, Form 1099-B, trial balance |
| `openbooks.doctor` | installation, provider and model-integrity checks |

Until 0.1.0 these were six separate packages (`openbooks-core`, `openbooks-statements`, `openbooks-gateways`, `openbooks-tax`,
`openbooks-doctor` and this one as a meta package). After upgrading, `openbooks doctor` tells you how to remove the old ones.

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.

> **Status: 0.2, pre-release.** Every layout has been exercised on synthetic fixtures only, not on real exports, and PayPal, Wise
> and all the tax layouts are experimental. Do not rely on it for real filings.

## Formats and limits

- Limits: 2 GB per document. Text formats (`.csv`, `.ofx`, `.qfx`, `.sta`, `.mt940`, `.txt`, `.xml`) are capped at 64 MB.
- Scans and images (`.pdf`, `.png`, `.jpg`, `.jpeg`) need the `[scan]` extra for OCR. Excel workpapers (`.xlsx`) are also accepted.
- Everything is tested on synthetic fixtures only.

## Links

- Developer docs: https://openbooks.lumeo.co.in/docs
- MCP server (`@lumeo_hq/openbooks-mcp` on npm): https://openbooks.lumeo.co.in/docs/mcp
- Source: https://github.com/Sagexd08/OpenBooks

Licence: Apache-2.0.
