# Datasets (downloaded by `scripts/download_datasets.py` and `kaggle datasets download`)

Licences are as labelled by the host, not legally verified. Tier follows the PRD (1 real, 2 public synthetic).

| Local dir (`data/raw/`) | Source | Tier | Licence label | Note |
|---|---|---|---|---|
| funsd, funsd_original | nielsr/funsd + official zip | 1 | not verified | trained on (train split only) |
| cord_v2 | naver-clova-ix/cord-v2 | 1 | CC BY-SA 4.0 | share-alike: legal check; trained on (train+val) |
| sroie, kaggle_urbikn__sroie-datasetv2 | HF mirror + Kaggle | 1 | MIT (HF) / "other" (Kaggle) | not yet used in training |
| t1d_invoice_receipt | Ruqii/t1d-invoice-receipt-data | 1 | not verified | third-party mirror |
| doclaynet_base | pierreguillou/DocLayNet-base | 1 | CDLA-Permissive-1.0 | downloaded (3.6 GB), not yet used |
| rvl_cdip | aharley/rvl_cdip | 1 | not verified | downloaded (37 GB), not yet used |
| agami_indian_bank_statements | AgamiAI/Indian-Bank-Statements | 2 | Apache-2.0 | synthetic Indian statements |
| voxel51_invoices | Voxel51 | 2 | not verified | synthetic |
| kaggle_keyvanhamdi__huge-transactional-dataset | Kaggle | 2 | ODbL-1.0 | simulated rows, no images |
| kaggle_surajitsadhukhan__indian-grocery-tax-invoice-image-dataset | Kaggle | 1 | CC BY 4.0 | replacement for DocILE (Indian invoices) |
| kaggle_sushmithanarayan__expenses-receipt-ocr | Kaggle | 1 | not shown | receipts |
| kaggle_miadul__multi-document-dataset-for-ocr-document-ai-and-llm | Kaggle | 2 | not shown | multi-document OCR |
| kaggle_nikitpatel__invoice-ner-dataset | Kaggle | 1 | CC-BY-NC-SA-4.0 | NON-COMMERCIAL: do not train on until you decide |
| kaggle_farihmuhammad__synthetic-indonesian-bank-statements | Kaggle | 2 | MIT | synthetic |
| kaggle_coderanand__indian-banking-transaction-text-dataset | Kaggle | 2 | Apache-2.0 | text only |
| kaggle_devildyno__indian-bank-statement-one-year | Kaggle | 2 | CC0-1.0 | Account Aggregator CSV layout |
| kaggle_devildyno__upi-payment-transactions-dataset | Kaggle | 2 | MIT | UPI rows |
| kaggle_skullagos5246__upi-transactions-2024-dataset | Kaggle | 2 | CC0-1.0 | UPI rows |

## Not downloaded
- DocILE: gated, needs a token from docile.rossum.ai.
- BuDDIE: only unrelated name matches on HF (`aigen-de/buddie_full` unverified, not downloaded); see `data/download_log.json`.
- OCR Invoice (Mendeley 5n3jwggcjk): downloaded OK (`ocr_invoice_mendeley`), not yet used.
- Divyanshu97 bank statement model: excluded on purpose (cc-by-nc-sa-4.0).
