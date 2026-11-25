# OpenBooks ML pipeline

## Slice 1 complete

- Reproduced the shipped RoleNet synthetic baseline with its saved calibration. See [the model audit](docs/MODEL.md#shipped-baseline-audit).
- Training and rescoring now report per-role support, coverage, correct commitments, and false amount commitments from non-amount tokens. The rescore records artifact and corpus hashes plus runtime details.
- The shifted baseline committed 2,351 correct balances and zero debits or credits. The token gate accepted a constructed report with 100% abstention.
- Targeted verification passed 11 tests. The shipped model and calibration were kept in place.

## Slice 2

- Token gate implemented. It requires exact split fingerprints, consistent counts, and at least 1% correct commitment recall per debit and credit on each split, with the shipped counts as a floor. The shipped baseline has zero false amounts on both splits and sets the error ceiling.
- `gpu-full-01` failed the token gate on the same cache. It made zero debit or credit commitments and one false amount commitment on test. Both models released 24/24 expected releases with zero false releases on the 64-case synthetic suite without OCR scans. Run reports are under `out/roles/slice2/`.
- Froze and scored [independent synthetic holdout 01](docs/ROLE_HOLDOUT.md#independent-synthetic-holdout-01). It contains three publisher-supplied originals with 54 reconciled transactions and one one-paisa balance alteration per original. The 435 development PDFs are excluded from scoring.
- The original holdout run refused all six files. After fixing PDF glyph grouping and balance labels above the table, both bundles released all three originals with 54 of 54 exact matches per field, refused all three altered copies, and made zero false releases. The manifest stayed fixed. This cohort is now regression evidence for the parser change.
- `gpu-full-01` still fails the token gate. Keep the shipped bundle.
- The one bounded replacement run, `gpu-wide-families-12e`, trained for 12 epochs on the cached wide and three-family splits. It passed both file checks but failed the unchanged token gate: shifted coverage was 96.32%, neither debit nor credit committed correctly on shifted layouts, and false amount commitments increased.
- The frozen cohort is regression evidence for these layouts. Independent, consented redacted customer statements and second-reviewer adjudication remain open for production qualification.

## Arithmetic pipeline

- For a fully headerless PDF or scan, RoleNet proposes token roles and the resolver searches for a unique complete balance chain. A typed refusal covers unresolved or multiple readings. The standard proof, field evidence, and schema gate still determine release.
- On 60 synthetic headerless PDFs, exact releases rose from 45 to 52 with the shipped int8 bundle. Both runs made zero false releases. See [model architecture and results](docs/MODEL.md#2-where-it-sits-in-the-pipeline).
- [Shifted direction experiment](docs/ROLE_HOLDOUT.md#shifted-direction-research): calibration alone recovered coverage with zero shifted direction commitments. On a fresh 48-document shift split, arithmetic proof raised correct commitments to 130 debit and 230 credit with zero wrong amounts. The proof-only ablation matched the learned head. The original promotion gate and shipped artifacts are still in place.

## Replay cache handoff

- [Build and verify instructions](docs/MODEL.md#6-training-and-shipping). New synthetic caches retain the extracted words, geometry, and labels alongside their token pickle.
- The [PDFium smoke report](out/roles/replay-cache-text-01/verification-current.json) rebuilt 147 windows and replayed 324 proof direction assignments with zero label mismatches. The normal shipped-model rescore used the same split fingerprints.
- The [historical text-layer backfill](out/roles/replay-cache-legacy-native-01/verification-current.json) reconstructed 1,800 documents and matched all 2,196 regenerated windows against ordered prefixes of the original cache. This covers 282 of 353 ordinary test windows and 182 of 246 shifted windows. Proof replay made 6,496 direction assignments with zero label mismatches. The local reconstruction runner is `out/roles/try_legacy_text_replay.py`.
- Historical EasyOCR probes did not reproduce the legacy scan fingerprints. The [versioned OCR rebuild](out/roles/replay-cache-ocr-v2/verification.json) regenerated all 330 scans, saved evidence for 404 replacement OCR windows, and verified all 2,600 windows including the 2,196 exact original text-layer windows. Keep the original corpus and its verdict with their original fingerprints.
- The [v2 token gate](out/roles/replay-cache-ocr-v2/token-verdict.txt) rejected `gpu-wide-families-12e` after both bundles were rescored on identical splits. Shifted coverage was 96.36%, and the candidate had two wrong amount commitments on the ordinary test.
- The [v2 proof replay](out/roles/replay-cache-ocr-v2/proof-score.json) passed the token criteria with the shipped model, yielding 854 correct shifted debits and 1,179 credits, 98.82% shifted coverage, and zero wrong amounts. It yielded 967 correct commitments across the ordinary and shifted OCR splits. This was an offline proof evaluation. Production weights and role serving remain as shipped.
