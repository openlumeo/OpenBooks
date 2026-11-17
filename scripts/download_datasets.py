"""Download every public dataset named in the PRD. Small first, RVL-CDIP last.
Usage: python scripts/download_datasets.py [--skip-large]
Writes data/raw/<name>/ and data/download_log.json. Re-runnable (HF cache resumes).
Licences are NOT checked here; see docs/DATASETS.md.
"""
import json, sys, time, urllib.request, zipfile
from pathlib import Path
from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
LOG = ROOT / "data" / "download_log.json"

HF = [
    ("funsd", "nielsr/funsd", 1, "licence not verified"),
    ("sroie", "priyank-m/SROIE_2019_text_recognition", 1, "MIT per UNIKIE-BENCH"),
    ("cord_v2", "naver-clova-ix/cord-v2", 1, "CC BY-SA 4.0: share-alike, legal check"),
    ("agami_indian_bank_statements", "AgamiAI/Indian-Bank-Statements", 2, "synthetic, Apache 2.0"),
    ("t1d_invoice_receipt", "Ruqii/t1d-invoice-receipt-data", 1, "third-party mirror, verify"),
    ("voxel51_invoices", "Voxel51/high-quality-invoice-images-for-ocr", 2, "synthetic"),
    ("doclaynet_base", "pierreguillou/DocLayNet-base", 1, "CDLA-Permissive-1.0"),
    ("rvl_cdip", "aharley/rvl_cdip", 1, "LARGE (~40 GB); licence not verified"),
]
URLS = [
    ("funsd_original", "https://guillaumejaume.github.io/FUNSD/dataset.zip", "dataset.zip"),
    ("ocr_invoice_mendeley", "https://data.mendeley.com/public-api/zip/5n3jwggcjk/download/1", "mendeley.zip"),
]
BLOCKED = {
    "docile": "Needs a registration token from docile.rossum.ai (gated). Ask user to register.",
    "kaggle_keyvanhamdi_transactions": "Needs Kaggle API credentials (~/.kaggle/kaggle.json). Not available.",
    "kaggle_sroie_urbikn": "Needs Kaggle API credentials. HF mirror of SROIE downloaded instead.",
}


def log_write(log):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")


def find_buddie(api):
    try:
        return [d.id for d in api.list_datasets(search="buddie", limit=10)]
    except Exception as e:
        return [f"search failed: {e}"]


def main():
    skip_large = "--skip-large" in sys.argv
    api = HfApi()
    log = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "results": {}, "blocked": BLOCKED}
    for name, repo, tier, note in HF:
        if skip_large and name == "rvl_cdip":
            log["results"][name] = {"status": "skipped", "note": note}
            continue
        dest = RAW / name
        try:
            print(f"[{name}] {repo} ...", flush=True)
            snapshot_download(repo_id=repo, repo_type="dataset", local_dir=dest, max_workers=8)
            log["results"][name] = {"status": "ok", "repo": repo, "tier": tier, "note": note}
        except Exception as e:
            log["results"][name] = {"status": "failed", "repo": repo, "error": str(e)[:300]}
        log_write(log)
    for name, url, fname in URLS:
        dest = RAW / name
        dest.mkdir(parents=True, exist_ok=True)
        try:
            print(f"[{name}] {url} ...", flush=True)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest / fname, "wb") as f:
                f.write(r.read())
            if zipfile.is_zipfile(dest / fname):
                with zipfile.ZipFile(dest / fname) as z:
                    z.extractall(dest / "extracted")
            log["results"][name] = {"status": "ok", "url": url}
        except Exception as e:
            log["results"][name] = {"status": "failed", "url": url, "error": str(e)[:300]}
        log_write(log)
    log["buddie_search"] = find_buddie(api)
    log["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    log_write(log)
    print(json.dumps({k: v["status"] for k, v in log["results"].items()}, indent=2))


if __name__ == "__main__":
    main()
