# The typed role heads: how the model works

This is the only learned model in Open Books. It is a small layout-aware encoder that reads the words of a PDF or scan and says, for every word, **which column of a bank statement it sits in** and **what kind of value it is**. It never releases a document. It can only add refusals.

Source: `packages/py/openbooks/src/openbooks/statements/` (`encoder.py`, `roles.py`, `calibration.py`, `labels.py`). Weights and calibration: `models/`. Served directly by `POST /v1/roles` (see [SERVING.md](SERVING.md)). Measured cost: [PROFILE_ROLES.md](PROFILE_ROLES.md).

## 1. What it is, and what it is not

| It is | It is not |
|---|---|
| A 18.9M-parameter bidirectional transformer **encoder** with two classification heads | A language model. No text generation, no KV cache, no autoregressive loop |
| Trained from scratch on **synthetic** statements only | Pretrained on anyone's documents. No third-party dataset and no real client file went into the shipped weights |
| A **cross-check** with abstention | A source of truth. The balance gate (opening + sum of amounts = closing, row by row) always has the last word |

Because it is an encoder run once per window of words, ideas that belong to decoders (PagedAttention, speculative decoding, KV caches) do not apply to it. `docs/HANDOFF.md` parks those until a decoder is approved.

## 2. Where it sits in the pipeline

```
PDF / scan
   │  PDFium text layer, or the configured OCR provider         (pdf_front.read_words)
   ▼
words per page: text, box (x0,y0,x1,y1), page size
   │
   ├──────────────► rule-based extractor (header words → columns) ─┐
   │                                                                │
   ▼                                                                ▼
 TYPED HEADS  ── role + value type + conformal sets per word ──► crosscheck / fallback
   (this doc)                                                       │
                                                                    ▼
                                              balance gate (always has the last word)
                                                                    │
                                     ┌──────────────────────────────┴───────────────┐
                                     ▼                                              ▼
                         one openbooks.v1 JSON per file                   typed refusal
                        (evidence method "pdf_text+model"                (LOW_CONFIDENCE when the heads
                         or "ocr+model")                                  disagree or will not commit)
```

Two jobs, both opt-in with `--model` (the "Model cross-check" box in the web app):

1. **Cross-check** (`roles.crosscheck`). The column the rule-based extractor chose for every date and amount word must lie inside the model's conformal set. Otherwise the file is refused with `LOW_CONFIDENCE`. This can only add refusals.
2. **Header-less fallback** (`Predictions.resolve_chain`). RoleNet provides allowable debit, credit, and balance roles for each token. On a fully headerless statement, the arithmetic specialist checks candidate assignments across successive rows and against the available opening and printed closing balances. It uses exact decimal arithmetic and retains at most two distinct running balances per row. If two interpretations converge on the same balance, it remembers the ambiguity. A unique chain advances to the usual proof and schema gates. Zero or multiple chains produce `LOW_CONFIDENCE`. Mixed documents use the row-local fallback until the first header is found.

On 60 identical synthetic headerless PDFs using the shipped int8 bundle, row-local resolution released 45 exact results and document-wide resolution released 52. Both had zero incorrect releases. Exactness requires the same ordered dates, directions, amounts, and running balances. This measures the contribution of arithmetic search with the model held fixed. [Benchmark results](evidence/s2b_document_chain.json)

## 3. Input: what the model sees per word

A page's words are sorted into reading order (`round(y/4)`, then `x`) and cut into **windows of at most 512 tokens** (`encoder.windows`). Each window becomes one sequence. Per word the model receives:

| Feature | How it is built | Why |
|---|---|---|
| Word identity | `crc32(lowercase text)` into 16,384 hash buckets | No vocabulary to maintain; unseen words are just another hash |
| Word shape | digits→`d`, upper→`A`, lower→`a`, runs collapsed, plus length ≤ 12, hashed into 512 buckets | `12,345.67` and `Rs.` look alike across statements |
| Box | `x0, y0, x1, y1` scaled to 0–1000 by page size, plus width and height | LayoutLM-style 2D position |
| Position | index within the window | Reading order |
| Row features | among money-shaped words on the same line: **rank from the right** (cap 4) and **count in the row** (cap 6) | A row reads `description … [debit] [credit] balance`, so the balance is always rank 0. Geometry only: no header words, no extractor output |
| Column header words | for each money word, the up-to-3 hashed words of the nearest non-money line above it in the same x-range | The model learns what `Withdrawal Amt.` or `Money Out` means. No header vocabulary is coded anywhere, so a new wording is a new hash, not a new rule |

## 4. Architecture

```
 word-hash ─┐
 shape-hash ─┤
 x0,x1 ──────┤ (shared x table)
 y0,y1 ──────┤ (shared y table)
 width ──────┤
 height ─────┤──► sum ──► pre-norm TransformerEncoder ──► LayerNorm ──┬─► Linear(384→6)  role
 position ───┤           6 layers · width 384 · 6 heads                │
 row rank ───┤           FFN 1536 · GELU · dropout 0.1                 └─► Linear(384→4)  value type
 row count ──┤
 header words (sum of up to 3 word embeddings, shared word table)
```

| Part | Size |
|---|---|
| Word table 16,384 × 384 (also used for header words) | 6.3 M |
| Shape 512 × 384, x/y/width/height 4 × 1,001 × 384, position 512 × 384, rank, count | 1.9 M |
| Transformer, 6 layers (≈ 1.77 M each) | 10.6 M (43 MB in fp32) |
| Heads | 0.004 M |
| **Total** | **18.9 M** (`models/roles_model_card.json`: 18,878,602) |

Outputs per word:

- **Role** (6): `other, date, desc, debit, credit, balance`
- **Value type** (4): `text, date, money, code`

## 5. Calibration and abstention

Raw logits are not trusted directly. `calibration.py` applies, per head:

1. **Temperature scaling**: `softmax(logits / T)`.
2. **Split-conformal prediction set**: class `k` is in the set when `1 − p_k ≤ qhat`. `qhat` is fitted on held-out calibration windows so the true class is in the set with probability `1 − alpha`.

A word is **committed** only when its role set holds exactly one class. Any other size is an **abstention**. Shipped `alpha` is **0.001**. The numbers live in `models/roles_calibration.json`, which also stores the **sha256 of the weights it was fitted on**. `RoleModel.load` refuses to start on a mismatch, so a retrain with an old calibration (or the reverse) can never load silently. Every `--model` release records both hashes in `file.model`.

The coverage guarantee holds only when calibration and test data are exchangeable. On a layout unlike anything in the calibration set it can fail; that is why the model is a cross-check, not a gate.

## 6. Training and shipping

- **Data**: synthetic statements from `openbooks_lab.synth` (default layouts plus the three families `sign`, `branch`, `skew`). Random initialisation, no pretrained weights. The 50 M JEPA encoder in `models/jepa_encoder.pt` was pretrained on CORD (CC BY-SA), is internal-only, git-ignored, and is deliberately not loadable by the package.
- **Recipe** (`scripts/train_roles.py`): AdamW, encoder lr 3e-4, heads lr 1e-3, weight decay 0.01, batch 16, 6 epochs by default, optional label smoothing or focal loss, wide-header augmentation. Calibration is fitted on its own split plus the wide-header split and the calibration windows of every trained family.
- **At rest**: int8, per-row symmetric scales for every 2-D weight with ≥ 4,096 elements, fp16 for the rest. **19.04 MB**. Dequantised to fp32 on load (about 1 s the first time including PyTorch, then cached per process).
- **Token screening gate** (`scripts/promote.py`): both evaluation splits must match the shipped split fingerprints and per-role label counts. Debit and credit must each correctly commit on at least 1% of their labeled tokens per split and meet the shipped counts. Wrong amount commitments, including non-amount tokens predicted as amounts, may not increase. Shifted coverage must reach 0.98 and the test amount top-1 accuracy may drop by at most 0.005.

Run the candidate workflow from the repository root with the training dependencies installed:

```bash
python scripts/train_roles.py 1200 150 6 --alpha 0.001 --out out/roles/candidate-01
python scripts/verify_roles.py out/roles/candidate-01 --scans
```

Training records runtime versions, source and dataset hashes, and FP32 and int8 metrics. Use `--refresh-data` after changing the synthetic generator. The cache contains local pickle files generated by the training scripts. Calibration is fitted again on the quantized model using the serving precision. Use `scripts/score_calibrated.py --help` to rescore saved artifacts against a local split cache.

For arithmetic research, generate the cache with the [replay cache tool](../scripts/role_replay_cache.py). Each evidence record stores one synthetic document's extracted text, geometry, extraction method, and source digest. The verifier reconstructs the ordered token windows and labels from this evidence. The proof replay receives the extracted pages only.

```powershell
.venv/Scripts/python.exe scripts/role_replay_cache.py build out/roles/replay-cache --text 80
.venv/Scripts/python.exe scripts/role_replay_cache.py verify out/roles/replay-cache --replay
```

The generated `tokens.pkl` works with `score_calibrated.py --dataset`. Use `verify --against <trusted-local-pickle>` to check exact matching prefixes and full split identity against an older cache. Compare models on the same full cache and retain the original fingerprint if the evidence only covers part of it.

To rebuild the missing scans while retaining the verified legacy text windows, run the resumable rebuild with CUDA and the local EasyOCR models. Each completed scan has its own checkpoint. Re-run the same command to resume after an interruption. The manifest and verification report identify the rebuilt corpus separately from the original cache.

```powershell
$cache = 'out/roles/replay-cache-ocr-v2'
python scripts/rebuild_role_ocr.py out/roles/replay-cache-legacy-native-01 data/roles_dataset_1200_150.pkl $cache
python scripts/score_calibrated.py --dataset "$cache/tokens.pkl" --out "$cache/shipped-rescore.json"
python scripts/score_calibrated.py --model-dir out/roles/gpu-wide-families-12e --dataset "$cache/tokens.pkl" --out "$cache/candidate-rescore.json"
python scripts/promote.py --baseline "$cache/shipped-rescore.json" "$cache/candidate-rescore.json"
python scripts/score_role_replay_proof.py $cache out/roles/gpu-wide-families-12e --out "$cache/proof-score.json"
```

Verification loads the saved checkpoint and calibration, compares its int8 metrics with the shipped baseline, and runs synthetic files through the public pipeline. It writes `verification.json` and `file_evaluation.json` beside the candidate. The gate checks release decisions, false accepts, output shape, model identity, and payout matching. A pass is a review signal. Candidate commands leave shipped weights and evidence files in place.

To exercise the wiring on a CPU, use `python scripts/train_roles.py 8 0 1 --device cpu --threads 2 --out out/roles/smoke`. Verification should reject this run against the shipped baseline because its held-out split is much smaller.

On CUDA, use `--batch-size` to fit training to the available GPU memory and `--fp32` to compare against mixed precision. The metrics record training throughput, stage times and peak allocated GPU memory. See the [production ML roadmap](ML_ROADMAP.md) for the next evaluation and rollout milestones.

The default baseline is `docs/evidence/roles_metrics_token_baseline.json`, recorded from the shipped weights and calibration. To screen on a different synthetic split cache, rescore both models on that same trusted cache and run `promote.py --baseline <shipped-rescore> <candidate-rescore>`. Bundle verification uses the candidate metrics recorded in the bundle.

### Shipped baseline audit

On 25 November 2026, this command scored the shipped weights with their saved calibration on the original synthetic cache using CUDA and PyTorch 2.14.1+cu126.

```powershell
python scripts/score_calibrated.py --out out/roles/slice1/shipped.json
```

| Metric | Test | Shifted |
|---|---:|---:|
| Labeled amount tokens | 18,195 | 11,685 |
| All-role prediction-set coverage | 99.97% | 98.79% |
| Amount prediction-set coverage | 99.99% | 99.98% |
| Amount top-1 accuracy | 90.10% | 76.96% |
| Correct debit singletons / true debit tokens | 56 / 3,619 | 0 / 2,333 |
| Correct credit singletons / true credit tokens | 125 / 4,776 | 0 / 3,066 |
| Correct balance singletons / true balance tokens | 6,128 / 9,800 | 2,351 / 6,286 |
| Wrong predicted amount singletons / all predicted amount singletons | 0 / 6,309 | 0 / 2,351 |

Historical coverage and amount error counts reproduced. Differences in reported rounded rates were at most 0.0003. The new report records model, calibration and corpus hashes, execution device, and per-role counts. Its prediction-side error counts include dates, descriptions and other tokens committed as amounts. Prediction-set coverage measures whether a set contains the true role. A singleton is the only set size the model will commit to.

The shifted split produced zero debit and credit commitments. The token screen now requires 24 and 31 respectively and rejects a report with 100% abstention. The shipped metrics had zero false amount commitments on both splits, which sets the current error ceiling. The file-level checks evaluate release decisions.

Evaluate the next challenger on frozen documents grouped by source and template, keeping related scans and variants together. Report document-level uncertainty, exact transaction fields and false releases. DocILE's unseen-layout protocol is a reference for split design. Weighted conformal requires justification for the target shift and defensible density-ratio estimates. Conformal Risk Control is a candidate only where the document-level loss meets its assumptions. [DocILE](https://arxiv.org/abs/2302.05658) · [Weighted conformal under covariate shift](https://papers.neurips.cc/paper_files/paper/2019/hash/8fb21ee7a2207526da55a679f0332de2-Abstract.html) · [Conformal Risk Control](https://proceedings.iclr.cc/paper_files/paper/2024/file/f3549ef9b5ff520a7e41ff3cc306ab2b-Paper-Conference.pdf)

## 7. What was measured (synthetic data; see `docs/HANDOFF.md` S3b and `docs/evidence/`)

| Measure | Shipped candidate |
|---|---|
| Shifted-split coverage / confident-wrong | 0.988 / 0 |
| Test confident-wrong | 0 |
| Test amount accuracy | 0.901 |
| Test abstention | 0.653 |
| Unseen layout families, abstention | 0.67 – 0.83 |

On AgamiAI's synthetic Digital Type 1 `00001.pdf` (6 pages, 2,611 words), the heads abstained on **96.86%** of words. The digital parser can read the records, and the running-balance gate refuses the file because its balances do not reconcile. See [the dataset pilot](DATASET_PILOT.md) for extraction and release baselines.

## 8. Inference cost

From [PROFILE_ROLES.md](PROFILE_ROLES.md), RTX 3050 6 GB laptop GPU:

- The encoder is **compute-bound, not memory-bandwidth-bound**: about 28 GB/s implied against 157 GB/s measured copy bandwidth; matrix multiplies are 87% of kernel time.
- A real request is dominated by **CPU work**: PDF word extraction ≈ 100 ms and feature building ≈ 45 ms, against a 35–43 ms GPU forward for a 6-page file.
- Batching the windows of a document (done in `server/openbooks_server/inference.py`) cut model time by about 18% with logits equal to the stock path within 5e-6.
- fp16 would make the forward about 2.3× faster and agreed on 99.92% of role sets, but the calibration is fitted on fp32 logits, so it is **not enabled**.

## 9. Limits to remember

- Trained on synthetic data only; real layouts abstain heavily.
- Windows are capped at 512 words, so a page with more words is cut into several sequences.
- Hash buckets collide by design; they trade a small amount of accuracy for no vocabulary.
- The heads read one file at a time. Linking payouts to bank credits is a separate, rule-based step (`openbooks_lab.link`).
