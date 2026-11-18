# openbooks-statements

Providers for bank statements, registered with `openbooks-core`.

| Input | Install | How it is proven |
|---|---|---|
| bank CSV (`bank_csv.v1`), OFX, MT940 | `pip install openbooks-statements` (pure Python) | opening + movements = closing, running balance ties on every row |
| PDF with a text layer | `pip install "openbooks-statements[pdf]"` (adds pypdfium2) | same chain, with page and bounding box evidence per field |
| scans and photos | `pip install "openbooks-statements[scan]"` (adds EasyOCR, PyTorch, Pillow) | same chain; OCR dates are also checked to be in order, and low OCR confidence refuses |

Without the `[pdf]` extra a PDF is not a refusal about the document: the engine reports that pypdfium2 is missing (exit code 3).
PDFs are read with pypdfium2 (Apache-2.0 / BSD-3, wrapping Google's PDFium) and images with Pillow; nothing in this package is copyleft.
A page whose text layer is rotated (`/Rotate`) is refused rather than guessed; scans are rendered and read by OCR.

## Typed heads (`--model`)

`python -m openbooks_core run statement.pdf --model` cross-checks the column assignment with a small calibrated model. The heads
can only add refusals (`LOW_CONFIDENCE`); the balance gate always has the last word. The weights (`roles_head.pt`, about 19 MB)
and their calibration ship inside the wheel under `openbooks_statements/data/`, and the calibration names the sha256 of the exact
weights it was fitted on: a mismatch refuses to load. A released document records both hashes in `file.model`.
`OPENBOOKS_MODELS_DIR` overrides the location. Weights are loaded with `torch.load(..., weights_only=True)` (PyTorch 2.6 or newer).

All figures for the heads are on synthetic data. No accuracy claim has been measured on real client documents.

## Not here

Training, the synthetic data generator, calibration fitting and payout-to-bank-credit matching are not part of this package.
