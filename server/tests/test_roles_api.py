"""POST /v1/roles: the typed heads' own reading, served directly and batched across pages."""
import json

import numpy as np
import pytest

pytest.importorskip("torch")
from fastapi.testclient import TestClient  # noqa: E402
from openbooks.core.params import Params  # noqa: E402
from openbooks_server.app import app  # noqa: E402
from openbooks_server.inference import logits_batched  # noqa: E402
from openbooks.statements.pdf_front import read_words  # noqa: E402
from openbooks.statements.roles import RoleModel  # noqa: E402

ROLES = {"other", "date", "desc", "debit", "credit", "balance"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def pdf(client, tmp_path_factory):
    r = client.get("/v1/samples/ok_pdf_text")
    assert r.status_code == 200
    path = tmp_path_factory.mktemp("roles") / "ok_pdf_text.pdf"
    path.write_bytes(r.content)
    return path


@pytest.fixture(scope="module")
def model():
    m = RoleModel.load()
    if m is None:
        pytest.skip("no model weights in models/")
    return m


def post(client, path, params=None):
    data = {"params": json.dumps(params)} if params is not None else {}
    return client.post("/v1/roles", files={"file": (path.name, path.read_bytes())}, data=data)


def test_reading_of_a_pdf(client, pdf, model):
    r = post(client, pdf)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["schema_version"] == "openbooks.roles.v1"
    toks = [t for p in doc["pages"] for t in p["tokens"]]
    assert toks and doc["summary"]["tokens"] == len(toks)
    for t in toks:
        assert t["role"] in ROLES and set(t["role_set"]) <= ROLES
        assert t["abstained"] == (len(t["role_set"]) != 1)
        x0, y0, x1, y1 = t["box"]
        assert -0.01 <= x0 <= x1 <= 1.01 and -0.01 <= y0 <= y1 <= 1.01
    assert doc["model"] == model.identity  # same hashes a --model release records


def test_batched_logits_equal_the_stock_path(pdf, model):
    pages, _ = read_words(pdf, Params())
    words = [w for pg in pages for w in pg]
    r0, t0 = model.logits(words)
    r1, t1 = logits_batched(model, words, max_tokens=1024)  # small budget forces several batches
    assert np.abs(r0 - r1).max() < 1e-3 and np.abs(t0 - t1).max() < 1e-3
    assert model.role_cal.sets(r0) == model.role_cal.sets(r1)


def test_not_a_pdf_is_a_typed_refusal(client, tmp_path):
    csv = tmp_path / "bank.csv"
    csv.write_text("Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n")
    r = post(client, csv)
    assert r.status_code == 422
    assert r.json()["error"] == "UNSUPPORTED_INPUT"


def test_bad_params_are_rejected(client, pdf):
    assert post(client, pdf, {"ocr": "yes"}).status_code == 422
