"""Resume a full EasyOCR regeneration beside the verified legacy RoleNet text corpus."""
from __future__ import annotations

import argparse
import gzip
import json
import os
import pickle
import sys
from importlib.metadata import version
from pathlib import Path

import train_roles as tr
from openbooks.statements import pdf_front
from openbooks.statements.ocr_providers import PROVIDER_ENV
from role_candidates import sha256, write_json
from role_replay_cache import EVIDENCE, MANIFEST, TOKENS, Word, evidence_record, verify, write_manifest

SCAN_COUNT = 150


def write_checkpoint(path: Path, value: dict) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(path)


def rebuild(native: Path, original: Path, output: Path) -> None:
    text_report = verify(native, original)
    native_manifest = json.loads((native / MANIFEST).read_bytes())
    text_count = native_manifest["recipe"]["training_text_documents"]
    if text_count != 1200 or native_manifest["recipe"]["training_scan_documents"]:
        raise ValueError("expected the full legacy text-only corpus")
    if any(text_report["comparison"][split]["matching_prefix_windows"] != info["windows"]
           for split, info in text_report["splits"].items()):
        raise ValueError("native evidence does not match the original cache prefixes")

    recipe = tr.base_recipe(text_count, SCAN_COUNT)
    if any(text_report["splits"][split]["documents"] != n_text
           for split, (_, n_text, _) in recipe.items()):
        raise ValueError("native evidence does not contain all expected text documents")
    if not tr.torch.cuda.is_available():
        raise ValueError("CUDA is required for this EasyOCR rebuild")
    os.environ[PROVIDER_ENV] = "easyocr"
    tr.torch.set_num_threads(4)
    runtime = {name: version(name) for name in ("easyocr", "torch", "pymupdf", "pypdfium2",
                                               "Pillow", "numpy", "opencv-python-headless")}
    runtime.update(python=sys.version.split()[0], gpu=tr.torch.cuda.get_device_name())
    plan = {"original_sha256": text_report["comparison_sha256"],
            "native_manifest_sha256": text_report["manifest_sha256"],
            "reader": "PDFium and EasyOCR", "runtime": runtime,
            "recipe": {name: list(counts) for name, counts in recipe.items()},
            "source_sha256": {file.name: sha256(file) for file in (
                Path(__file__), Path(tr.__file__), Path(pdf_front.__file__),
                Path(sys.modules[tr.to_scan.__module__].__file__))}}
    output.mkdir(parents=True, exist_ok=True)
    checkpoint = output / "scan-checkpoints"
    plan_path = output / "rebuild-plan.json"
    if plan_path.exists() and json.loads(plan_path.read_bytes()) != plan:
        raise ValueError("checkpoint plan differs from the current inputs or runtime")
    if (output / MANIFEST).exists():
        write_json(output / "verification.json", verify(output, original, replay=True))
        print(f"Already verified: {output / MANIFEST}", flush=True)
        return
    checkpoint.mkdir(exist_ok=True)
    if not plan_path.exists():
        write_checkpoint(plan_path, plan)

    for split, (seed, n_text, n_scan) in recipe.items():
        expected = range(seed + n_text, seed + n_text + n_scan)
        if all((checkpoint / f"{doc_seed}.json").is_file() for doc_seed in expected):
            print(f"{split}: {n_scan}/{n_scan} OCR checkpoints already present", flush=True)
            continue
        print(f"{split}: generating {n_scan} OCR documents", flush=True)
        for doc_seed, scan, source, cells in tr.split_documents(seed, n_text, n_scan, shifted=split == "shifted"):
            if not scan:
                continue
            path = checkpoint / f"{doc_seed}.json"
            if not path.exists():
                pages, method = pdf_front.read_words(source, tr.Params(ocr=True))
                if method != "ocr" or set(pdf_front.last_ocr_engines()) != {"easyocr"}:
                    raise ValueError(f"document {doc_seed} did not use the expected EasyOCR path")
                write_checkpoint(path, evidence_record(split, doc_seed, source, method, pages, cells))
            complete = doc_seed - expected.start + 1
            if complete == 1 or complete % 10 == 0 or complete == n_scan:
                print(f"{split}: {complete}/{n_scan} OCR checkpoints", flush=True)

    splits = pickle.loads((native / TOKENS).read_bytes())
    with gzip.open(native / EVIDENCE, "rt", encoding="utf-8") as original_records, gzip.open(
            output / EVIDENCE, "wt", encoding="utf-8", newline="\n") as records:
        for line in original_records:
            records.write(line)
        for split, (seed, n_text, n_scan) in recipe.items():
            for doc_seed in range(seed + n_text, seed + n_text + n_scan):
                payload = (checkpoint / f"{doc_seed}.json").read_text(encoding="utf-8")
                record = json.loads(payload)
                if (record["split"], record["seed"], record["method"]) != (split, doc_seed, "ocr"):
                    raise ValueError(f"invalid OCR checkpoint: {doc_seed}")
                pages = [[Word(**word) for word in page] for page in record["pages"]]
                splits[split].extend(tr.items_of(pages, record["cells"]))
                records.write(payload)
    (output / TOKENS).write_bytes(pickle.dumps(splits))
    write_manifest(output, splits, text_count, SCAN_COUNT, rebuild=plan)
    write_json(output / "verification.json", verify(output, original, replay=True))
    print(f"Verified: {output / MANIFEST}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("native", type=Path)
    parser.add_argument("original", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rebuild(args.native, args.original, args.output)


if __name__ == "__main__":
    main()
