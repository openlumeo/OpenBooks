# RoleNet promotion holdout

Use the Agami pilot, the five Bankstatemently PDFs already smoke-tested, and the Indonesian degradation samples for development. Reserve independent statements with adjudicated labels for the promotion comparison. Assign the same `source_document` to a statement and all its rescans and augmentations. Assign the same `layout` to files that use the same template. Keep each source and layout in one split. The Agami audit already supplies transaction fingerprints for matching its digital and scanned copies.

Keep the roster, PDFs, and labels in an approved data location. Paths are relative to the roster. Use opaque IDs and paths if the frozen manifest will be shared. These example entries show the roster format.

```json
[
  {"id": "dev-01", "split": "development", "source_document": "source-01",
   "layout": "layout-a", "pdf": "dev/01.pdf"},
  {"id": "hold-01-scan", "split": "holdout", "source_document": "source-02",
   "layout": "layout-b", "pdf": "hold/01-scan.pdf", "truth": "truth/01.json", "currency": "INR"}
]
```

Supply an uppercase three-letter `currency` only when the normal release path needs it and it is known independently. The freeze records it as an input to both models.

Record the independently adjudicated decision and transactions in statement order. Record the printed balance, including any discrepancy. Use decimal strings to preserve precision. For a refusal whose rows cannot be established, use `null` for `transactions` and record the basis for that decision in the review referred to by `adjudication`.

```json
{
  "outcome": "released",
  "adjudication": "review-02",
  "transactions": [{"date": "2026-01-05", "direction": "debit", "amount": "2.50", "balance": "97.50"}]
}
```

Freeze before candidate scoring and retain the manifest as the reference for later verification.

```powershell
.venv/Scripts/python.exe -m scripts.freeze_role_holdout roster.json frozen.json
.venv/Scripts/python.exe -m scripts.freeze_role_holdout roster.json frozen.json --verify
```

The tool checks the declared groups, rejects identical PDF bytes, and pins each PDF and truth file by SHA-256. Establish group identities and confirm the completeness of the development roster during intake. A hash verifies file identity. Source provenance and label correctness depend on the review.

Compare shipped and candidate models on the same frozen files and runtime settings. Report exact date, direction, amount, and running balance, plus the number of false releases. Count a release as false if the expected decision is refusal or its released rows disagree with the reference. Group uncertainty estimates by `source_document` so rescans and augmentations contribute to the same independent unit.

## Score a candidate

```powershell
.venv/Scripts/python.exe -m scripts.score_role_holdout roster.json frozen.json out/roles/candidate > holdout-report.json
```

The scorer checks the frozen manifest and training bundle, then runs the shipped and candidate models through the normal PDF proof and release path in separate processes. Both use the same recorded currency, OCR, and thread settings. Include at least one expected release and one expected refusal. Keep the report in the approved data location. It contains document IDs, counts, refusal codes, and artifact hashes.

Document scores require the correct row count and exact ordered values for all four fields. Amounts and balances are compared as decimals. Field counts use the same denominator for both models, counting missing reference rows as unmatched. The report also gives the number of distinct source groups and, when there are zero false releases, a one-sided 95% upper bound on the source-group false-release probability under independent, identically distributed sampling. Treat the bound as descriptive when the cohort is small or selected.

The holdout gate rejects a candidate with any false release, zero correct releases, or a loss of any correct shipped release. Exit 0 means the holdout gate passed, 1 means it rejected the candidate, and 2 means the comparison could not be completed. Use this result alongside the existing token and synthetic release checks in `scripts/verify_roles.py` when reviewing promotion.

## Independent synthetic holdout 01

The three originals are the complete synthetic sample pack at [AyonPal commit `c781b5f`](https://github.com/AyonPal/bank-statement-pdf-parser/tree/c781b5fd41126dedc124dd9e5bc80016038bea5b/samples). Before scoring, an independent PDF text and position check matched the publisher's snapshots for all 54 dates, directions, amounts, and running balances. Decimal reconciliation matched each running balance and the printed closing balance. Each refusal control changes a single printed running balance by INR 0.01 and stays in its original's source group. A word-level PDF comparison verified the one-token change. The labels were machine cross-checked without a second human reviewer.

The freeze contains 6 holdout PDFs in 3 source groups and 435 development PDFs from Agami, Bankstatemently, and the Indonesian scan samples. Its SHA-256 is `5890cc880851939d1701050290466c4dee526870a65a469d97999608f19667cd`. Local roster, labels, adjudication, build script, frozen manifest, and evaluation reports are under `out/roles/independent-holdout-01/`.

| Bundle | Correct releases | Missed releases | Correct refusals | False releases |
| --- | ---: | ---: | ---: | ---: |
| Shipped | 0 | 3 | 3 | 0 |
| `gpu-full-01` | 0 | 3 | 3 | 0 |

Both bundles returned `UNKNOWN_LAYOUT` for all three originals and `PARSE_ERROR` for the three altered copies. The test therefore produced no released rows for field-accuracy comparison. The descriptive one-sided 95% upper bound for a source-group false release was 63.2% under independent, identically distributed sampling. Three synthetic originals from one publisher give limited safety evidence.

The candidate was rejected by the independent holdout and by the token gate on matching split fingerprints. It passed the synthetic regression suite without OCR with 24 of 24 expected releases, zero false releases, and 64 cases. The shipped weights and calibration stay in place. Keep these inputs frozen if a later candidate is evaluated against the same cohort.

### Rerun after the PDF parser fix

PDFium exposed many words as separate glyph objects. The parser now rejoins adjacent glyphs within whitespace boundaries on glyph-dominated pages. It also recognises currency-prefixed balances printed directly below their labels above a recognised table. The existing proof checks still control release.

The same frozen manifest passed on rerun. Shipped and `gpu-full-01` each released all three originals, matched 54 of 54 dates, directions, amounts, and running balances, and refused all three altered copies. The token-gate rejection still blocks promotion. This cohort informed the parser fix and is now regression evidence for those layouts. The rerun report is `out/roles/independent-holdout-01/holdout-report-pdf-fix.json`.

### Bounded replacement experiment

`gpu-wide-families-12e` ran for 12 epochs with cross-entropy loss, wide augmentation, and sign, branch, and skew family data from the existing caches. It used 3,068 training windows, 778 calibration windows, and alpha 0.001. The RTX 3050 run took 288 seconds for training and evaluation. The served int8 bundle was checked on the same token split fingerprints and frozen document cohort.

The candidate correctly committed 1,025 debit and 1,805 credit tokens in the ordinary test split, up from shipped counts of 56 and 125. On the shifted split, both counts were zero and role coverage was 96.32% against a 98% minimum. False amount commitments were 2 on test and 1 on shifted, against a ceiling of zero. The token gate rejected it. It passed the 64-case synthetic file regression and released all three originals with all 54 reference rows exact in the frozen cohort, with zero false releases in either run. The shipped bundle stays in place.

The local candidate bundle and combined token and synthetic gate report are under `out/roles/gpu-wide-families-12e/`. The frozen cohort rerun is `out/roles/independent-holdout-01/holdout-report-wide-families-12e.json`.

### Shifted direction research

On the original shifted tokens, the 12-epoch replacement's top role was correct for 42.1% of debits and 72.4% of credits before abstention. Refitting conformal thresholds per layout group and role restored 99.98% coverage and eliminated wrong commitments. Correct debit and credit commitments remained zero. A pooled refit of the shipped weights reached 98.20% coverage with the same zero commitments. The local diagnostics are in `out/roles/shift-diagnosis-01/`. Nominal conformal coverage assumes exchangeable data, so shifted acceptance is measured directly. [Classification with Valid and Adaptive Coverage](https://arxiv.org/abs/2006.02544)

One bounded follow-up used printed amounts and token geometry to train a small direction head on 1,368 tokens from 96 synthetic layouts. Temperature was fitted on 408 tokens from 24 other layouts. The head and probability threshold were fixed before generating the evaluation PDFs. A direction could commit only if RoleNet's set allowed it and the printed opening, closing, and all intervening rows admitted a unique arithmetic chain. A proof-only arm omitted the new head and used the same acceptance conditions.

| Method | Fresh ordinary debit / credit | Fresh shifted debit / credit | Shifted role coverage | Wrong amount commitments |
| --- | ---: | ---: | ---: | ---: |
| Shipped RoleNet sets | 1 / 5 | 0 / 0 | 99.29% | 0 |
| RoleNet with arithmetic proof | 132 / 193 | 130 / 230 | 99.29% | 0 |
| RoleNet with proof and learned head | 132 / 193 | 130 / 230 | 99.29% | 0 |

Both proof arms passed the existing token criteria applied to identical fresh splits. Each made zero proof commitments on 12 PDFs with a one-paisa closing-balance alteration. The two arms matched exactly on the measured decisions. This run supports using the proof with the existing model and provides no measured gain from deploying the new head.

```powershell
python scripts/research_direction_head.py --out out/roles/direction-head-reproduction
```

The [research harness](../scripts/research_direction_head.py) expects the training dependencies and shipped bundle. The original run saved its head, source and artifact hashes, split fingerprints, and metrics under `out/roles/direction-head-01/`. This is a research result on newly rendered text-layer PDFs. The original promotion cache has hashes and boxes but lacks the printed values needed to replay the proof. Its token verdict stays rejected, and production weights and role serving are unchanged.
