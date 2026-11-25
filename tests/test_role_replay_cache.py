import gzip
import json
from pathlib import Path

import pytest


def test_replay_cache_round_trips_and_rejects_misaligned_words(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    pytest.importorskip("pymupdf")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from role_replay_cache import EVIDENCE, MANIFEST, TOKENS, build, verify
    from scripts.role_candidates import sha256, write_json

    folder = tmp_path / "cache"
    build(folder, 4, 0)
    checked = verify(folder, folder / TOKENS, replay=True)
    assert all(split["exact"] for split in checked["comparison"].values())
    assert checked["splits"]["test"]["documents"] == 2
    assert checked["splits"]["shifted"]["documents"] == 1
    assert "proof_directions" in checked["splits"]["shifted"]
    with pytest.raises(FileExistsError):
        build(folder, 4, 0)

    evidence = folder / EVIDENCE
    records = gzip.decompress(evidence.read_bytes()).decode("utf-8").splitlines()
    first = json.loads(records[0])
    first["pages"][0][0]["text"] = "replacement token"
    records[0] = json.dumps(first)
    evidence.write_bytes(gzip.compress(("\n".join(records) + "\n").encode("utf-8")))
    with pytest.raises(ValueError, match="artifact changed"):
        verify(folder)

    manifest_file = folder / MANIFEST
    manifest = json.loads(manifest_file.read_bytes())
    manifest["artifacts_sha256"][EVIDENCE] = sha256(evidence)
    write_json(manifest_file, manifest)
    with pytest.raises(ValueError, match="differs from its token windows"):
        verify(folder)


def test_scan_rebuild_reuses_completed_checkpoints(tmp_path, monkeypatch):
    pytest.importorskip("torch")
    pytest.importorskip("pymupdf")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import rebuild_role_ocr as job
    from role_replay_cache import EVIDENCE, MANIFEST, TOKENS, Word, build, verify
    from scripts.role_candidates import write_json

    native, output = tmp_path / "native", tmp_path / "output"
    build(native, 4, 0)
    manifest_path = native / MANIFEST
    manifest = json.loads(manifest_path.read_bytes())
    manifest["recipe"]["training_text_documents"] = 1200
    write_json(manifest_path, manifest)
    recipe = {"train": (0, 4, 1), "calib": (10_000, 2, 1),
              "test": (20_000, 2, 1), "shifted": (30_000, 1, 1)}
    with gzip.open(native / EVIDENCE, "rt", encoding="utf-8") as stream:
        labels = {record["split"]: record for record in map(json.loads, stream)}

    def sources(seed, n_text, _n_scan, **kwargs):
        name = next(name for name, counts in recipe.items() if counts[0] == seed)
        yield seed + n_text, True, name.encode(), labels[name]["cells"]

    calls = []

    def read(source, params):
        name = source.decode()
        calls.append(name)
        if calls == ["train", "calib"]:
            raise ValueError("mock interruption")
        return [[Word(**word) for word in page] for page in labels[name]["pages"]], "ocr"

    monkeypatch.setattr(job.tr, "base_recipe", lambda *_: recipe)
    monkeypatch.setattr(job.tr, "split_documents", sources)
    monkeypatch.setattr(job.tr.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(job.tr.torch.cuda, "get_device_name", lambda: "fixture")
    monkeypatch.setattr(job, "version", lambda _: "fixture")
    monkeypatch.setattr(job.pdf_front, "read_words", read)
    monkeypatch.setattr(job.pdf_front, "last_ocr_engines", lambda: ("easyocr",))
    monkeypatch.setenv(job.PROVIDER_ENV, "easyocr")

    original = native / TOKENS
    with pytest.raises(ValueError, match="mock interruption"):
        job.rebuild(native, original, output)
    assert not (output / MANIFEST).exists()
    job.rebuild(native, original, output)
    assert calls == ["train", "calib", "calib", "test", "shifted"]
    result = verify(output, original)
    for name, (_, count, _) in recipe.items():
        assert result["splits"][name]["documents"] == count + 1
        assert result["comparison"][name]["matching_prefix_windows"] == result["comparison"][name]["original_windows"]


def test_unreadable_ocr_balance_anchor_produces_no_proof(monkeypatch):
    pytest.importorskip("torch")
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    from openbooks.statements.pdf_words import Word
    from research_direction_head import document_features

    words = [Word("Opening", 0, 0, 20, 10, 1), Word("Balance", 30, 0, 50, 10, 1),
             Word("1.234,56", 60, 0, 90, 10, 1)]
    assert document_features([words], None) == ({}, {})
