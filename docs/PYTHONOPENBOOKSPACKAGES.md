# Open Books Python packages

Financial documents in, **one proven JSON document per file out, or a typed refusal**. Never guessed. Never partially released.

Open Books reads bank statements, payment-gateway exports and tax documents into one canonical `openbooks.v1` record. A file is
released only if its numbers prove themselves: balances tie, totals match, and at least one check is independent evidence from the
document itself. Otherwise it is refused with a typed code. Every released field keeps its evidence (page, bounding box, row, raw
text, extraction method), and money is `Decimal` end to end, never a float, never rounded silently.

> **Status: 0.1.0, pre-release.** Every layout has been exercised on synthetic fixtures only, not on real exports. PayPal, Wise and
> all the tax layouts are experimental. Do not rely on it for real filings.

## Where to find them

All six packages are on PyPI, released together at the same version, under the Apache-2.0 licence.

| Package | PyPI | What it is |
|---|---|---|
| `openbooks` | https://pypi.org/project/openbooks/ | Meta package: installs everything below and keeps `import openbooks.pipeline` working |
| `openbooks-core` | https://pypi.org/project/openbooks-core/ | The `openbooks.v1` contract, normalisation, balance gates, layout registry and the `openbooks` CLI |
| `openbooks-statements` | https://pypi.org/project/openbooks-statements/ | Bank statements: CSV, OFX, MT940, PDFs, scans (OCR), optional typed-head model |
| `openbooks-gateways` | https://pypi.org/project/openbooks-gateways/ | Payment gateway exports: Stripe, Razorpay, PayPal, Wise |
| `openbooks-tax` | https://pypi.org/project/openbooks-tax/ | Tax and ledger documents: Form 26AS, AIS, FIRA, Form 1099-B, trial balance |
| `openbooks-doctor` | https://pypi.org/project/openbooks-doctor/ | `openbooks doctor`: checks an installation, its providers and model assets |

Each release ships a wheel (`py3-none-any`, pure Python) and a source distribution. Release history:
`https://pypi.org/project/<name>/#history`.

## Requirements

- Python **3.11 or newer** (3.11, 3.12 tested in CI on Linux and Windows).
- No compiler needed: every Open Books wheel is pure Python. The `[pdf]` extra pulls `pypdfium2`, which ships prebuilt binaries for
  common platforms.
- The `[scan]` extra installs PyTorch (2.6 or newer) and EasyOCR, which are large (several hundred MB to a few GB).

## Installation

Use a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
```

### Everything (recommended)

```bash
pip install openbooks              # core, statements with PDF support, gateways, tax, doctor
openbooks doctor                   # should end with "-> OK" and exit 0
```

Add OCR for scans and photos, and the typed-head model cross-check:

```bash
pip install "openbooks[scan]"
```

On Linux, the default PyTorch wheel is the CUDA build. For a much smaller CPU-only install, install PyTorch first:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install "openbooks[scan]"
```

### Only what you need

Each provider brings `openbooks-core` with it. Install only the families you read:

```bash
pip install openbooks-statements             # bank CSV, OFX, MT940 (pure Python, no PDF library, no PyTorch)
pip install "openbooks-statements[pdf]"      # + PDFs with a text layer (pypdfium2)
pip install "openbooks-statements[scan]"     # + scans and photos (EasyOCR, PyTorch, Pillow, NumPy) and --model
pip install openbooks-gateways               # Stripe, Razorpay, PayPal, Wise
pip install openbooks-tax                    # 26AS, AIS, FIRA, 1099-B, trial balance
pip install openbooks-doctor                 # installation checks
pip install openbooks-core                   # the engine alone (only jsonschema); refuses every file until a provider is installed
```

A missing provider never causes a guess: a file that looks like a known layout whose package is not installed is refused with the
name of the package to install.

### Pinning

All packages move in lock-step. Pin the same version everywhere:

```bash
pip install "openbooks==0.1.0"
```

Providers accept any `openbooks-core` in the same minor series (`>=0.1.0,<0.2`); the meta package pins exact versions.

### Upgrading and uninstalling

```bash
pip install --upgrade openbooks
pip uninstall openbooks openbooks-core openbooks-statements openbooks-gateways openbooks-tax openbooks-doctor
```

## Check the installation

```bash
openbooks doctor            # human-readable
openbooks doctor --json     # machine-readable, schema "openbooks.doctor.v1"
openbooks doctor --deep     # also imports PyTorch and loads the model
openbooks doctor --strict   # warnings fail too
```

Doctor checks the Python version, core and its schemas, that provider versions match core, that every provider imports, which known
layouts have no provider, the PDF and OCR dependencies, that the model weights match their calibration, and runs a built-in
self-test per layout (a balanced document must release and its tampered twin must be refused). It reads no user documents.
Without `[scan]` it shows one expected warning: `scan.dependencies: missing: torch, easyocr, PIL, numpy`.

## Supported documents

| Layout id | Document | Package | Proven by | Status |
|---|---|---|---|---|
| `bank_csv.v1` | bank statement CSV / `.xlsx` | statements | opening + movements = closing; running balance ties on every row | synthetic fixtures |
| `ofx.v1` | OFX bank statement | statements | same balance chain | synthetic fixtures |
| `mt940.v1` | SWIFT MT940 | statements | same balance chain | synthetic fixtures |
| PDF / scan | bank statement PDF, scanned page, photo | statements `[pdf]` / `[scan]` | same chain, with page and bounding box per field; OCR dates must be in order | synthetic fixtures |
| `stripe_balance.v1` | Stripe balance export | gateways | gross - fee - tax = net per row, totals, payout | synthetic fixtures |
| `razorpay_settlement.v1` | Razorpay settlement | gateways | same | synthetic fixtures |
| `paypal_activity.v1` | PayPal activity download | gateways | PayPal's own gross, fee and net columns | **experimental** |
| `wise_statement.v1` | Wise statement | gateways | running balance ties on every row | **experimental** |
| `tds_26as.v1` | Form 26AS | tax | printed totals of amount, tax deducted, tax deposited | **experimental** |
| `ais.v1` | Annual Information Statement | tax | printed total of reported value | **experimental** |
| `fira.v1` | Foreign inward remittance advice | tax | foreign amount x rate = INR amount within 0.01, INR - charges = net, totals | **experimental** |
| `form_1099b.v1` | Form 1099-B detail | tax | proceeds - cost basis + adjustment = gain/loss per row, totals | **experimental** |
| `trial_balance.v1` | Trial balance | tax | debits = credits, printed totals | **experimental** |

Accepted file types: `.csv`, `.txt`, `.xlsx`, `.ofx`, `.qfx`, `.sta`, `.mt940`, `.pdf`, and `.png`/`.jpg`/`.jpeg` for scans, up to
20 MB per file. Text must be UTF-8 or cp1252. Other 1099 forms have no arithmetic to prove and are not parsed. A printed total that is an Excel formula is not counted as independent evidence.

## Command line

`pip install openbooks-core` (or anything that depends on it) provides the `openbooks` command. `python -m openbooks_core ...` is
the same command.

```bash
openbooks run statement.csv --currency INR --opening 1000.00 --out out
```

| Command | Does |
|---|---|
| `openbooks run FILE [FILE ...]` | process each file, write one `openbooks.v1` JSON per file to `--out` (named `<sha256 of the file>.json`) |
| `openbooks report FOLDER` | run every file in a folder and write `report.json`; a `params.json` in the folder gives per-file currency, opening, account |
| `openbooks link FILE [FILE ...]` | link settlement payouts and FIRA credits to bank credits (needs a linker plugin; none ships in 0.1) |
| `openbooks eval ROOT` | run a golden set and report mismatches and false accepts |
| `openbooks engine-info` | print the engine version, contract version and installed layouts as JSON |
| `openbooks doctor` | installation checks (with `openbooks-doctor` installed) |

Options for `run` and `report`:

| Option | Meaning |
|---|---|
| `--out DIR` | where the JSON documents are written |
| `--currency CODE` | ISO currency when the document does not state one (for example `INR`, `USD`) |
| `--opening AMOUNT` | opening balance, if the file does not state one |
| `--account ID` | account identifier to record |
| `--allow-derived-opening` | allow an opening balance derived from the first row instead of stated or supplied |
| `--date-order dmy\|mdy` | day/month order of numeric dates; inferred from the file when omitted, refused when it cannot be proven |
| `--no-ocr` | refuse scans instead of running OCR |
| `--model` | cross-check PDFs and scans with the typed heads (needs `[scan]`); can only add refusals |
| `--machine` | (`run` only) print one JSON object per file on stdout, then an `{"engine": ...}` line; for wrappers |

Exit codes: `0` everything released, `1` at least one file was refused, `2` usage error, `3` the engine could not run (for example a
missing optional dependency). A refusal still writes its JSON document; an engine fault does not.

Example with a balanced file and a tampered copy:

```bash
$ openbooks run statement.csv tampered.csv --currency INR --opening 1000.00 --out out --machine
{"code": null, "file": "statement.csv", "output": "out/5e7b...2485.json", "status": "ok"}
{"code": "BALANCE_MISMATCH", "file": "tampered.csv", "output": "out/f6d9...32e1.json", "status": "refused"}
{"engine": {...}}
$ echo $?
1
```

## Python API

```python
from decimal import Decimal
from pathlib import Path

from openbooks_core import Params, process

doc = process(Path("statement.csv"), Params(currency="INR", opening=Decimal("1000.00")))

if doc["status"] == "ok":
    for t in doc["data"]["transactions"]:
        print(t["date"], t["direction"], t["amount"]["amount"], t["amount"]["currency"])   # amounts are strings
else:
    print(doc["error"]["code"], doc["error"]["message"])                                  # a refusal is a value, not an exception
```

`Params` fields: `currency`, `opening` (a `Decimal`, not a string), `account`, `allow_derived_opening`, `ocr` (default `True`),
`model` (default `False`), `date_order` (`"dmy"`, `"mdy"` or `None`).

Other public names in `openbooks_core`: `validate_output`, `load_schema`, `SCHEMA_VERSION`, `Refusal`, `ProviderMissing`,
`EngineFault`, `Registry`, `default_registry`, and the normalisers `to_dec`, `to_date`, `date_order`, `money`, `fmt`.
Existing code that does `from openbooks.pipeline import process, Params` keeps working with the `openbooks` meta package.

## Output

A released document:

```json
{
  "schema_version": "openbooks.v1",
  "status": "ok",
  "file": { "name": "statement.csv", "sha256": "5e7b...2485", "detected_format": "csv", "layout_version": "bank_csv.v1",
            "method": "parser" },
  "data": { "accounts": [], "parties": [], "batches": [], "transactions": [], "claims": [] },
  "evidence": { "batch-1.closing": { "page": null, "bbox": null, "row": 3, "raw_text": "1300.00", "method": "parser" } },
  "assertions": [ { "id": "A1", "rule": "batch-1: opening + sum(txns) = closing", "expected": "1300.00 INR",
                    "computed": "1300.00 INR", "passed": true, "independent": true } ]
}
```

With `--model`, `file` also carries `model: { weights_sha256, calibration_sha256 }`. A transaction:

```json
{ "id": "txn-00001", "batch_id": "batch-1", "account_id": "acct-1", "date": "2026-01-01", "direction": "credit",
  "amount": { "amount": "500.00", "currency": "INR" }, "balance_after": { "amount": "1500.00", "currency": "INR" },
  "description": "Opening deposit", "reference": null }
```

A refusal carries no partial data:

```json
{
  "schema_version": "openbooks.v1",
  "status": "refused",
  "data": null,
  "error": {
    "code": "BALANCE_MISMATCH",
    "message": "batch-1: opening + sum(txns) = closing (expected 1310.00 INR, got 1300.00 INR); ...",
    "file_sha256": "f6d9931335bbfae5a09ba00179e875dafc62c137d2806a0a5d5460fd1ae132e1"
  }
}
```

Refusal codes:

| Code | Meaning |
|---|---|
| `BALANCE_MISMATCH` | the document's own numbers do not tie (balance chain, totals, per-row arithmetic) |
| `UNKNOWN_LAYOUT` | no known layout matches, or it matches a layout whose provider package is not installed (the message names the package) |
| `UNSUPPORTED_INPUT` | the file type, size (over 20 MB), encoding or structure is not accepted (for example an encrypted PDF, a rotated text layer) |
| `PARSE_ERROR` | the layout matched but a value could not be read safely (ambiguous date, malformed amount, missing column) |
| `LOW_CONFIDENCE` | OCR confidence or the typed heads did not support a confident reading |
| `OUTPUT_INVALID` | the built document failed the `openbooks.v1` JSON Schema or a required gate was missing |

An unexpected internal error is also refused (`PARSE_ERROR`) and marked `error.internal: true`.
The JSON Schemas ship inside `openbooks-core` (`openbooks_core/schema/openbooks.v1.schema.json` and
`openbooks.v1.refusal.schema.json`); load them with `openbooks_core.load_schema()`.

## The typed-head model (`--model`)

`openbooks-statements` ships a small calibrated model (`roles_head.pt`, about 19 MB) with its calibration and model card inside the
wheel under `openbooks_statements/data/`. With `[scan]` installed, `openbooks run statement.pdf --model` cross-checks the column
assignment. The heads can only add refusals (`LOW_CONFIDENCE`); the balance gate always has the last word.

- The calibration names the sha256 of the exact weights it was fitted on; a mismatch refuses to load.
- A released document records both hashes in `file.model`.
- Weights load with `torch.load(..., weights_only=True)` (PyTorch 2.6 or newer).
- `OPENBOOKS_MODELS_DIR` overrides where the assets are read from.
- All model figures are on synthetic data; no accuracy claim has been measured on real client documents.

## Troubleshooting

| Symptom | Fix |
|---|---|
| exit code `3` and "PDF and image statements need pypdfium2" | `pip install "openbooks-statements[pdf]"` (included in `pip install openbooks`) |
| exit code `3` on a scan or with `--model` | `pip install "openbooks[scan]"` |
| `UNKNOWN_LAYOUT` naming a package | install that package, for example `pip install openbooks-gateways` |
| `PARSE_ERROR` about date order | pass `--date-order dmy` or `--date-order mdy` |
| a bank file without a stated opening balance is refused (`PARSE_ERROR`) | pass `--opening AMOUNT`, or `--allow-derived-opening` |
| `versions.lockstep` fails in doctor | upgrade all packages together: `pip install --upgrade openbooks` |
| `ERROR: ... requires a different Python` | use Python 3.11 or newer |

## Releasing a new version (maintainers)

Publishing is automated by `.github/workflows/publish-pypi.yml` with PyPI Trusted Publishing (no tokens). Each PyPI project trusts
`Sagexd08/OpenBooks`, workflow `publish-pypi.yml`, and its own GitHub environment:

| Project | Environment |
|---|---|
| openbooks-core | `pypi` |
| openbooks-statements | `pypi-statements` |
| openbooks-gateways | `pypi-gateways` |
| openbooks-tax | `pypi-tax` |
| openbooks-doctor | `pypi-doctor` |
| openbooks | `pypi-openbooks` |

1. Bump the version in every `packages/py/openbooks-*/src/openbooks_*/_version.py`, and the `version` and the `==` pins in
   `packages/py/openbooks/pyproject.toml`. All six must match (the workflow checks).
2. Build and check locally: `python -m build --sdist --wheel packages/py/<name>` per package, `twine check --strict dist/*`, and
   `OB_PACKAGING=1 python -m pytest tests/packaging`.
3. Commit, push, then tag: `git tag py-vX.Y.Z && git push origin py-vX.Y.Z`. The workflow builds, checks and uploads in dependency
   order (core first, the `openbooks` meta package last).

A version can never be uploaded twice. To withdraw a bad release, yank it on PyPI and publish the next version.

## Licence

Apache License 2.0 for all six packages and the shipped model files. Dependencies keep their own licences; all are permissive
except `python-bidi` (LGPL), pulled in by EasyOCR under the optional `[scan]` extra.
