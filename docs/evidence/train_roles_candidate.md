# RoleNet candidate: retrain on more synthetic data

Scope: a candidate retrain of `RoleNet` (scripts/train_roles.py recipe) on about 3x the shipped training windows, scored on the identical held-out splits. Synthetic statements only. Shipped weights in `models/` and `data/` were not modified. Candidate files live in `models/candidate/` (gitignored).

## Held-out protocol (unchanged)

The shipped test and shifted splits are the `test` and `shifted` keys of `data/roles_dataset_1200_150.pkl`. The candidate and the shipped model were both scored on those exact pickled windows. Split hashes below match the shipped `split_sha256` values.

- test: 65,099 tokens (18,195 amount tokens), sha256 `62c71b82...ae75ac`
- shifted: 44,186 tokens (11,685 amount tokens), sha256 `040d04a7...b09018`

Calibration for both models is refit with `openbooks_lab.calibration_fit.fit_calibrator` on the shipped `calib` split at alpha 0.01, using the same `report()` function from `scripts/train_roles.py`. This is an apples-to-apples comparison, not the shipped alpha 0.001 calibration.

## Training data

| | Shipped recipe | Candidate |
|---|---|---|
| Train windows | 1,620 (1,200 text pages + 150 OCR pages, seed 0) | 4,905 (3.03x) |
| Source | `data/roles_dataset_1200_150.pkl` | same pickle + 3 extra generated sets |
| Extra text pages | - | 2,400 (seed 60000) + 300 (seed 80000) |
| Extra OCR pages | - | 60 (seed 70000) |
| Extra windows | - | 3,285 |

The extra pages come from the repo's own generator (`make_split` in `scripts/train_roles.py`, which calls `openbooks_lab.synth`). The seed ranges are disjoint from the shipped train (0), calibration (10000), test (20000), shifted (30000) and wide (40000, 50000) seeds. Note: the OCR part is 60 pages, not 150 x 3. A 300-page OCR run measured about 10 s per scan, roughly 50 minutes, which would have blown the time cap. The OCR share is therefore 1.4x the shipped OCR pages rather than 3x. Total windows are still 3.03x.

## Training

- Recipe: unchanged from `train_roles.py` (AdamW, encoder lr 3e-4, heads lr 1e-3, weight decay 0.01, batch 16, 6 epochs, cosine schedule, fp16 autocast, seed 1, loss `ce`).
- Hardware: RTX 3050 6GB laptop GPU, torch 2.14.1+cu126 (global Python). Peak GPU memory was not logged; `nvidia-smi` showed about 1.5 GB in use.
- Training time: 238 s (4,905 windows x 6 epochs).
- Parameters: 18.88M (same architecture as shipped).

## Results (same held-out splits, same metric, both refit at alpha 0.01)

| Metric | Shipped | Candidate |
|---|---|---|
| Test amount role accuracy | 0.901 | **0.910** |
| Test amount singleton rate | 0.781 | 0.803 |
| Test amount singleton wrong (count) | 77 | 117 |
| Test role coverage | 0.991 | 0.990 |
| Test role ECE after temperature | 0.0075 | 0.0032 |
| Shifted amount role accuracy | 0.770 | **0.798** |
| Shifted amount singleton wrong (count) | 86 | 201 |
| Shifted role coverage | 0.925 | 0.904 |
| Shifted role ECE after temperature | 0.0837 | 0.0787 |
| Shifted amount abstain rate | 0.501 | 0.429 |

Shipped `models/roles_model_card.json` and `docs/MODEL.md` report shifted coverage 0.988 and test confident-wrong 0 at alpha 0.001. Those numbers use the shipped alpha-0.001 calibration, so they are not directly comparable to the refit figures above. Not measured here: shipped weights scored with their own shipped calibration JSON.

## Reading

- Test amount accuracy is about 0.9 points higher for the candidate.
- Confident-wrong singletons rise: 0.42% to 0.64% of test amount tokens, and 0.74% to 1.72% on shifted. Shifted coverage drops by 2 points. The candidate is not better on the safety-relevant measures.
- Verdict: the candidate is **not an improvement** and should not be promoted. The promotion gate in `docs/MODEL.md` (shifted coverage >= 0.98, confident-wrong <= baseline) would fail. More synthetic data alone did not buy safer abstention.

## Artifacts

- `models/candidate/roles_head.pt` (int8 state, same format as shipped)
- `models/candidate/roles_calibration.json` (temperature, qhat, alpha for role and vtype heads)
- `models/candidate/roles_metrics.json` (full report, shifted and test, parameters, train windows, seconds)
- Scratch driver and extra pickles: `C:\Users\sohom\AppData\Local\Temp\claude\44519c9abf3b6271\44bf0d49-a4b4-4f25-a6a3-24bc8fe2d467\scratchpad\driver.py`, `extra_text.pkl`, `extra_text2.pkl`, `extra_ocr.pkl`, logs `train.log`, `shipped_eval.json`.

## Commands

```
# Shipped baseline on the pickled held-out splits (driver imports scripts/train_roles.py unchanged)
python driver.py shipped

# Extra synthetic data, disjoint seeds
python -c "import sys; sys.argv=['x','gen']; sys.path.insert(0,'.'); import driver as D, pickle; from pathlib import Path; x=D.T.make_split(60000,2400,0); Path('extra_text.pkl').write_bytes(pickle.dumps(x))"
python -c "import sys; sys.argv=['x','gen']; sys.path.insert(0,'.'); import driver as D, pickle; from pathlib import Path; x=D.T.make_split(70000,0,60); Path('extra_ocr.pkl').write_bytes(pickle.dumps(x))"
python -c "import sys; sys.argv=['x','gen']; sys.path.insert(0,'.'); import driver as D, pickle; from pathlib import Path; x=D.T.make_split(80000,300,0); Path('extra_text2.pkl').write_bytes(pickle.dumps(x))"

# Train on shipped train + extra, evaluate, write candidate
python driver.py train
```

## Blockers and limits

- The `--out` path of `scripts/train_roles.py` cannot be used as-is: its test split size depends on the page count, which would change the held-out set. The driver reuses the shipped pickle's test and shifted splits instead.
- OCR extra data was limited by generation speed (see above).
- Single seed (1). No variance estimate.
- Synthetic data only. No real statements were scored.
- Repo changes: added `models/candidate/` to `.gitignore`. No other repo source files edited.
