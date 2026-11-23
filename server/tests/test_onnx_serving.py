import copy
from pathlib import Path

import numpy as np
import pytest
import torch

ROOT = Path(__file__).resolve().parents[2]
ONNX = ROOT / "models" / "onnx" / "role-net.onnx"
SAMPLE = ROOT / "data/raw/agami_indian_bank_statements/train/India_Bank_Statement_Digital_Type1/00003.pdf"

pytestmark = pytest.mark.skipif(not (ONNX.is_file() and SAMPLE.is_file()), reason="ONNX export or sample statement missing")


def test_onnx_logits_match_torch(monkeypatch):
    pytest.importorskip("onnxruntime")
    from openbooks.core.params import Params
    from openbooks.statements.pdf_front import read_words
    from openbooks.statements.roles import RoleModel
    from openbooks_server import inference

    model = RoleModel.load()
    cpu_model = copy.copy(model)
    cpu_model.net = copy.deepcopy(model.net).cpu()
    cpu_model.dev = torch.device("cpu")
    pages, _ = read_words(SAMPLE, Params(ocr=False))
    words = [word for page in pages for word in page]
    reference = inference.logits_batched(cpu_model, words)
    monkeypatch.setenv(inference.ONNX_ENV, str(ONNX))
    served = inference.logits_batched(inference.onnx_model(model), words)
    assert (reference[0].argmax(1) == served[0].argmax(1)).all()
    assert float(np.abs(reference[0] - served[0]).max()) < 1e-3


def test_onnx_model_is_identity_without_env(monkeypatch):
    from openbooks_server import inference

    monkeypatch.delenv(inference.ONNX_ENV, raising=False)
    sentinel = object()
    assert inference.onnx_model(sentinel) is sentinel
