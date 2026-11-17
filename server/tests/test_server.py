import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from openbooks_server.app import app

BANK = "Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance\n"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def events(resp) -> list[tuple[str, dict]]:
    out = []
    for block in resp.text.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def sample(client, case_id) -> tuple[str, bytes]:
    r = client.get(f"/v1/samples/{case_id}")
    assert r.status_code == 200
    name = r.headers["content-disposition"].split("filename=")[1].strip('"')
    return name, r.content


def run(client, files, params=None, file_params=None):
    data = {}
    if params is not None:
        data["params"] = json.dumps(params)
    if file_params is not None:
        data["file_params"] = json.dumps(file_params)
    return client.post("/v1/runs", files=[("files", f) for f in files], data=data)


def engine_layouts() -> set[str]:
    """Every layout id the engine source can put in file.layout_version."""
    import inspect
    import re

    from openbooks import parsers_extra, parsers_more, pdf_front, pipeline

    src = "".join(inspect.getsource(m) for m in (pipeline, parsers_extra, parsers_more, pdf_front))
    return set(re.findall(r'"([a-z0-9_]+\.v1)"', src)) - {"openbooks.v1"}


def test_health_and_formats(client):
    h = client.get("/v1/health").json()
    assert h["schema_version"] == "openbooks.v1" and h["max_bytes"] == 20 * 1024 * 1024
    f = client.get("/v1/formats").json()
    assert [g["title"] for g in f["groups"]] == ["Bank statements", "Gateway settlements", "Tax documents", "Excel workpapers"]
    assert {u["layout"] for u in f["unverified"]} <= engine_layouts() and all(u["name"] for u in f["unverified"])


def test_model_status_applies_the_engines_hash_binding(tmp_path):
    import hashlib

    from openbooks_server.catalog import model_status

    w, c = tmp_path / "w.pt", tmp_path / "cal.json"
    assert model_status(w, c) == (False, "no model weights (models/roles_head.pt)")
    w.write_bytes(b"weights-v2")
    assert model_status(w, c) == (False, "no calibration (models/roles_calibration.json)")
    c.write_text(json.dumps({"weights_sha256": "0" * 64}), encoding="utf-8")
    ready, issue = model_status(w, c)
    assert not ready and "calibration was fitted for other weights" in issue
    c.write_text(json.dumps({"weights_sha256": hashlib.sha256(b"weights-v2").hexdigest()}), encoding="utf-8")
    assert model_status(w, c) == (True, None)


def test_catalog_lists_exactly_the_layouts_the_engine_emits(client):
    listed = {lay for g in client.get("/v1/formats").json()["groups"] for lay in g["layouts"]}
    engine = engine_layouts()
    assert {"paypal_activity.v1", "wise_statement.v1", "form_1099b.v1", "bank_statement_pdf.v1"} <= engine  # the scan works
    assert listed == engine, f"missing from catalog: {engine - listed}; not in engine: {listed - engine}"


PAYPAL_AMBIGUOUS = (
    "Date,Time,TimeZone,Name,Type,Status,Currency,Gross,Fee,Net,Transaction ID,Balance Impact\n"
    "01/05/2026,10:00:00,PST,Acme,Payment,Completed,USD,100.00,-3.20,96.80,T1,Credit\n"
    "02/03/2026,12:00:00,PST,Bob,Payment,Completed,USD,-50.00,0.00,-50.00,T3,Debit\n"
)


def test_date_order_reaches_the_engine(client):
    f = ("paypal.csv", PAYPAL_AMBIGUOUS.encode())
    refused = [d["doc"] for e, d in events(run(client, [f])) if e == "file.done"][0]
    assert refused["error"]["code"] == "PARSE_ERROR" and "supply --date-order" in refused["error"]["message"]
    for order, first in (("mdy", "2026-01-05"), ("dmy", "2026-05-01")):
        doc = [d["doc"] for e, d in events(run(client, [f], {"date_order": order})) if e == "file.done"][0]
        assert doc["status"] == "ok" and doc["data"]["transactions"][0]["date"] == first
    per_file = [d["doc"] for e, d in events(run(client, [f], {}, {"0": {"date_order": "mdy"}})) if e == "file.done"][0]
    assert per_file["status"] == "ok"


def test_samples_list_featured_first(client):
    s = client.get("/v1/samples").json()["samples"]
    assert s[0]["id"] == "ok_bank_csv" and s[0]["featured"] and s[0]["filename"] == "ok_bank_csv.csv"
    assert s[0]["params"] == {"opening": "1000.00", "currency": "INR"}
    assert not any(k.startswith("_") for k in s[0])
    assert client.get("/v1/samples/nope").status_code == 404


def test_released_file_streams_every_stage_in_order(client):
    name, body = sample(client, "ok_bank_csv")
    r = run(client, [(name, body)], {"opening": "1000.00", "currency": "INR"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    ev = events(r)
    assert [e for e, _ in ev] == ["file.started"] + ["file.stage"] * 5 + ["file.done", "run.done"]
    assert ev[0][1] == {"index": 0, "name": "ok_bank_csv.csv", "size": len(body)}
    assert [d["stage"] for e, d in ev if e == "file.stage"] == ["detect", "parse", "normalise", "balance", "validate"]
    doc = ev[-2][1]["doc"]
    assert doc["status"] == "ok" and doc["file"]["name"] == "ok_bank_csv.csv"
    assert ev[-1][1] == {"released": 1, "refused": 0}


def test_tampered_file_is_refused_and_per_file_params_apply(client):
    ok = sample(client, "ok_bank_csv")
    bad = sample(client, "bad_bank_balance_break")
    no_open = sample(client, "bad_bank_no_opening")
    r = run(client, [ok, bad, no_open], {"opening": "1000.00", "currency": "INR"}, {"2": {"opening": ""}})
    done = {d["index"]: d["doc"] for e, d in events(r) if e == "file.done"}
    assert done[0]["status"] == "ok"
    assert done[1]["error"]["code"] == "BALANCE_MISMATCH"
    assert done[2]["error"]["code"] == "PARSE_ERROR" and "opening" in done[2]["error"]["message"]
    assert events(r)[-1] == ("run.done", {"released": 1, "refused": 2})


@pytest.mark.parametrize("params,needle", [
    ({"opening": "1,000.0.0"}, "opening balance"),
    ({"currency": "RUPEES"}, "currency"),
    ({"ocr": "yes"}, "ocr"),
    ({"date_order": "ymd"}, "date_order"),
])
def test_bad_params_are_rejected_before_any_file_runs(client, params, needle):
    r = run(client, [("a.csv", b"x")], params)
    assert r.status_code == 422 and needle in r.json()["detail"]


def test_file_params_must_point_at_a_file(client):
    r = run(client, [("a.csv", b"x")], {}, {"3": {"currency": "INR"}})
    assert r.status_code == 422


def test_too_many_files(client):
    r = run(client, [(f"{i}.csv", b"x") for i in range(21)])
    assert r.status_code == 422


def test_hostile_filename_stays_inside_the_run_dir(client):
    name, body = sample(client, "ok_bank_csv")
    r = run(client, [("../../evil.csv", body)], {"opening": "1000.00", "currency": "INR"})
    doc = [d for e, d in events(r) if e == "file.done"][0]["doc"]
    assert doc["status"] == "ok" and doc["file"]["name"] == "evil.csv"


def test_temp_files_are_removed(client):
    before = {p.name for p in Path(tempfile.gettempdir()).glob("openbooks-run-*")}
    name, body = sample(client, "ok_bank_csv")
    run(client, [(name, body)], {"opening": "1000.00", "currency": "INR"})
    after = {p.name for p in Path(tempfile.gettempdir()).glob("openbooks-run-*")}
    assert after <= before


def test_link_settlement_payout_to_bank_credit(client):
    rzp = sample(client, "ok_razorpay")
    bank = ("bank.csv", (BANK + "08/01/2026,RAZORPAY SETTLEMENT setl_1,,77.64,1077.64\n").encode())
    r = run(client, [rzp, bank], {"opening": "1000.00", "currency": "INR"})
    docs = [d["doc"] for e, d in events(r) if e == "file.done"]
    assert [d["status"] for d in docs] == ["ok", "ok"], docs
    links = client.post("/v1/link", json={"docs": docs}).json()
    assert links["schema_version"] == "openbooks.links.v1"
    assert len(links["links"]) == 1 and links["links"][0]["amount"] == {"amount": "77.64", "currency": "INR"}


def test_link_rejects_garbage(client):
    assert client.post("/v1/link", json={"docs": "nope"}).status_code == 422
