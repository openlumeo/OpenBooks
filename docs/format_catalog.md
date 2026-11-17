# Format catalog and rung-1 plan (research, slice S1)

Scope: bank-statement role heads only (date, desc, debit, credit, balance). 26AS/AIS/FIRA/Stripe/Razorpay go through parsers_extra, not the model.
All values in generated data stay synthetic. Sources are vendor articles and third-party docs, not bank specifications; treat as leads.

## What the sources support
- No uniform statement format; one bank can have several (SBI: app, desktop, branch-printed; HDFC: net-banking, corporate, legacy export). Source: terra-insight.com insight articles (vendor).
- Header vocabulary seen: Date / Txn Date / Transaction Date / Value Date / Posted Date / Dr/Cr Date / Trans Date; Debit / Dr / Withdrawal(s) / Debit Amount / With. Amt. / Amount Debited / Paid Out; Credit / Cr / Deposit(s) / Dep. Amt. / Amount Credited / Paid In; Balance / Closing / Running / Balance (Dr/Cr) / Available / Book / Bal.; Description / Particulars / Narration / Remarks / Transaction Details / Trans. Particulars; Ref No. / UTR / UTR Number / Transaction ID.
- Amounts: split Debit+Credit columns, OR one Amount column with Dr/Cr marker (suffix, e.g. "25000.00 Cr"), OR one Amount column plus a separate +/- or Dr/Cr indicator column. Balance may carry a Dr/Cr suffix or a separate Dr/Cr indicator column.
- Dates: 05/09/2026, 05-Sep-2026, 05-09-26. Txn date and value date can both print and differ by a day.
- Narration: prefixes UPI/, NEFT CR-, BY TRANSFER, IMPS/; private banks long, PSU/co-op short and sometimes cut off; cheque number in its own column or inside the narration.
- PSU branch printouts can be dot-matrix scans; private-bank PDFs often password-protected.

## Not stated by sources (general knowledge, UNVERIFIED; build only if you accept the risk)
page header blocks, summary boxes with totals, brought-forward/carried-forward rows, bracketed or trailing-minus negatives, lakh grouping rules.

## Generator gap (synth.py as of this slice)
Has: split and single-Amount layouts with Cr/Dr marker, Rs. prefix, serial/tid/vdate columns, Dr/Cr balance suffix, wrapped-above descriptions, watermarks, failed rows, 3 fonts, western/indian/plain grouping, 2-digit-year dates (wide only).
Missing: separate +/- indicator column; separate Dr/Cr column after balance; truncated PSU narrations and dot-matrix style; BY TRANSFER / NEFT CR- prefixes; txn/value date skew; header words "With. Amt.", "Dep. Amt.", "Trans. Particulars", "UTR Number", "Balance (Dr/Cr)", "Book Balance", bare "Dr"/"Cr" headers; distractor blocks (header, summary, B/F, footer).
Caution: "Paid Out/Paid In", "Money Out", "Payments", "Receipts" overlap the SHIFT_HEAD vocabulary. Keep the shifted test words out of training or the shifted split stops being a test.

## Proposed families (S2)
- F1 sign-indicator: single Amount + separate +/- or Dr/Cr column; balance with separate Dr/Cr column.
- F2 branch-print: Courier, truncated narration, short headers ("Date" only), cheque number inside narration, noisy scan.
- F3 skew: txn/value date skew, 2-digit year, new header words above, new narration prefixes.
- F4 distractors (UNVERIFIED structure): page header block, summary box with totals, B/F and C/F rows, footer. Hold this family out entirely as the first unseen-family test.

## Algorithms and schema found
- Weighted conformal (Tibshirani 2019) restores coverage under covariate shift, but needs the density ratio between calibration and target; we have no target sample. It can undercover when the ratio is learned or unbounded; effective sample size (sum w)^2 / sum w^2 is the diagnostic. Concept drift (P(y|x) changes) has no distribution-free guarantee; adaptive conformal inference is the fallback. Sources: arXiv 2411.11824, 2405.06627, 2605.02072.
- Practical use here: leave-one-family-out calibration. Fit qhat without family X, measure coverage on X; gives an honest unseen-layout number, which the guarantee alone does not.
- Related work: Spatial ModernBERT (arXiv 2507.08865) uses token classification with column/row heads, close to our design; TabSniper (arXiv 2412.12827) built BankTabNet for bank statements. Check dataset licences before any use (this repo keeps CC BY-SA and NC data out of anything shipped).
- No result found for synthetic-data/domain-randomization on this exact task; a practitioner claim of ~2,000 samples per class is a non-peer-reviewed blog figure.
- Schema: ReBIT Account Aggregator deposit FI schema (specifications.rebit.org.in; v2.0.0 reported published 2025-01-23 by third-party pages). Account -> Profile, Summary (currentBalance), Transactions with txnId, type, mode, amount, currentBalance, transactionTimestamp, valueDate, narration, reference. Our output adds per-field evidence and assertions, which ReBIT lacks. Optional later: an export mapper to the ReBIT shape. No change to the current output schema.

## Research round 2 (abstention, bytes, production). Search snippets only; read each paper before relying on a number.
- Abstention = prediction sets with more than one role. Shrinking sets at the same coverage: RAPS (penalty on low-prob classes), SAPS (label-rank score instead of softmax mass; arXiv 2310.06430), ConfTS (tune the temperature to minimise set size; arXiv 2402.04344), test-time augmentation (arXiv 2505.22764). Reported ImageNet gains (e.g. 14.6 -> 2.3 sets) come from other models and data; ours must be measured.
- Constraints: Lazy-k (EMNLP 2023, arXiv 2312.03367) decodes token labels under arithmetic constraints (e.g. total = paid - change) by searching consistent assignments. Conformal KIE (IJDAR 2026, s10032-026-00572-y) reports dates/prices give small sets, rare fields large. Our balance chain is the strongest constraint available: enumerate role assignments inside each set, keep those where debit/credit/balance tie, resolve only when exactly one survives. The balance proof stays the release gate.
- Bytes: BLT (arXiv 2412.09871) and ByT5 (arXiv 2105.13626) are tokenizer-free; both report better noise robustness. No OCR-specific numbers found. For us: a byte-level (256-symbol) word embedding in place of hashed word ids could generalise to unseen header spellings (the shifted-split failure). Not the earlier bit-level encoder, which overfit and was rejected. User's own "bite-size decoding" paper is NOT in the repo or session: title/link needed.
- NPU: Ryzen AI Software (ryzenai.docs.amd.com; onnxruntime.ai Vitis-AI-ExecutionProvider docs): needs Windows 11 >= 22621.3527, installer sets up conda env, Vitis AI quantizer, ONNX Runtime + VitisAI EP; int8 PTQ to ONNX; unsupported ops fall back. A 7640HS was on an older (1.0.1) support list; confirm on the current page. NPU runs inference only.
- Production checklist: ONNX int8 parity test (argmax and abstain identical to torch int8 on the test split); fix SCHEMA gaps (page/bbox, `independent`); regenerate manifest source hashes (stale after comment strip); per-family golden regressions; determinism and version stamps in output.
