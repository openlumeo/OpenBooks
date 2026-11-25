# OpenBooks ML pipeline

## Slice 1 complete

- Reproduced the shipped RoleNet synthetic baseline with its saved calibration. See [the model audit](docs/MODEL.md#shipped-baseline-audit).
- Training and rescoring now report per-role support, coverage, correct commitments, and false amount commitments from non-amount tokens. The rescore records artifact and corpus hashes plus runtime details.
- The shifted baseline committed 2,351 correct balances and zero debits or credits. The token gate accepted a constructed report with 100% abstention.
- Targeted verification passed 11 tests. The shipped model and calibration were kept in place.

## Slice 2

- Token gate implemented. It requires exact split fingerprints, consistent counts, and at least 1% correct commitment recall per debit and credit on each split, with the shipped counts as a floor. The shipped baseline has zero false amounts on both splits and sets the error ceiling.
- `gpu-full-01` failed the token gate on the same cache. It made zero debit or credit commitments and one false amount commitment on test. Both models released 24/24 expected releases with zero false releases on the 64-case synthetic suite without OCR scans. Run reports are under `out/roles/slice2/`.
- Build a frozen holdout grouped by source document and layout. Keep alternate scans and augmentations of a document together. Use the Agami pilot as development evidence and reserve independent documents for promotion.
- The five local Bankstatemently PDFs lack reference transactions and adjudicated release decisions. The Indonesian scan samples provide degradation labels only. The promotion comparison needs independent labeled documents before it can measure exact fields, false releases, and document-level uncertainty.
