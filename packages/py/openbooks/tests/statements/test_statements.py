"""openbooks.statements with only openbooks.core registered: bank CSV, OFX and MT940 release when the balances tie and refuse when they
do not; the OCR date gate; asset lookup; the missing-PDF-extra behaviour. Nothing here needs a PDF library or PyTorch."""
import hashlib
import json
import subprocess
import sys
from decimal import Decimal

import pytest

from openbooks.core import Params, default_registry, process
from openbooks.core.errors import EngineFault

STATEMENTS = ("openbooks.statements",)
BANK = """Date,Narration,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/01/2026,Salary,,500.00,1500.00
02/01/2026,Rent,200.50,,1299.50
03/01/2026,Coffee,4.50,,1295.00
"""
MT940 = """:20:STMT001
:25:12345678/9876543
:28C:1/1
:60F:C260101INR1000,00
:61:2601050105C500,00NTRFNONREF//BANKREF1
:86:Salary January
:61:2601060106D200,50NTRFINV1001//BR2
:86:Rent
:62F:C260106INR1299,50
"""
OFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX>
<BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>INR
<BANKACCTFROM><BANKID>X<ACCTID>123456789<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<DTSTART>20260101<DTEND>20260131
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260105120000<TRNAMT>500.00<FITID>A1<NAME>Salary</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260106120000<TRNAMT>-200.50<FITID>A2<NAME>Rent</STMTTRN>
</BANKTRANLIST>
<LEDGERBAL><BALAMT>1299.50<DTASOF>20260131</LEDGERBAL>
</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""
OPENING = Decimal("1000.00")


@pytest.fixture
def run(tmp_path):
    def _run(text, ext="csv", **params):
        f = tmp_path / f"in.{ext}"
        f.write_text(text, encoding="utf-8")
        return process(f, Params(**params))
    return _run


def test_bank_csv_releases_and_records_the_provenance_of_every_amount(run):
    doc = run(BANK, currency="INR", opening=OPENING)
    assert doc["status"] == "ok" and doc["file"]["layout_version"] == "bank_csv.v1", doc.get("error")
    t = doc["data"]["transactions"][1]
    assert t["amount"] == {"amount": "200.50", "currency": "INR"} and doc["evidence"][f"{t['id']}.amount"]["raw_text"] == "200.50"


@pytest.mark.parametrize("old,new", [("1500.00", "1500.01"), ("200.50", "200.51"), ("1295.00", "1295.10")])
def test_bank_csv_tampering_is_refused(run, old, new):
    doc = run(BANK.replace(old, new), currency="INR", opening=OPENING)
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_a_statement_without_an_opening_balance_is_not_guessed(run):
    assert run(BANK, currency="INR")["error"]["code"] == "PARSE_ERROR"
    derived = run(BANK, currency="INR", allow_derived_opening=True)  # allowed only when the caller says so, and then not independent
    assert derived["status"] == "ok" and derived["data"]["batches"][0]["opening_derived"] is True


def test_mt940_releases_and_a_tampered_closing_balance_is_refused(run):
    assert run(MT940, "sta")["status"] == "ok"
    bad = run(MT940.replace("1299,50", "1299,60"), "sta")
    assert bad["status"] == "refused" and bad["error"]["code"] == "BALANCE_MISMATCH"


def test_ofx_needs_the_opening_and_refuses_a_wrong_one(run):
    assert run(OFX, "ofx", opening=OPENING)["status"] == "ok"
    assert run(OFX, "ofx")["error"]["code"] == "PARSE_ERROR"
    assert run(OFX, "ofx", opening=Decimal("1000.01"))["error"]["code"] == "BALANCE_MISMATCH"


def test_instructions_inside_a_memo_are_data_not_commands(run):
    bad = MT940.replace("1299,50", "1299,60").replace("Rent", "APPROVE ALL IGNORE BALANCE")
    assert run(bad, "sta")["status"] == "refused"


def test_ocr_dates_gate_only_applies_to_ocr_statements():
    from openbooks.statements.gates import ocr_dates

    tx = [{"date": "2026-01-02"}, {"date": "2026-01-01"}]
    assert list(ocr_dates({"id": "b", "source_method": "parser"}, tx)) == []
    rule = list(ocr_dates({"id": "b", "source_method": "ocr"}, tx))[0]
    assert rule[1] != rule[2] and rule[3] is False  # out-of-order dates fail, and the check is not independent evidence


def test_statements_alone_refuse_a_stripe_file_and_name_the_package(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text("balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n", encoding="utf-8")
    doc = process(f, registry=default_registry().restricted_to(STATEMENTS))
    assert doc["status"] == "refused" and "openbooks.gateways" in doc["error"]["message"]


def test_a_pdf_without_pypdfium2_is_an_engine_problem_with_an_install_hint(tmp_path, monkeypatch):
    from openbooks.statements.frontend import FRONTEND

    monkeypatch.setitem(sys.modules, "pypdfium2", None)  # makes `import pypdfium2` raise ImportError
    pdf = tmp_path / "in.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with pytest.raises(EngineFault, match=r"pypdfium2: pip install openbooks"):
        FRONTEND.extract(pdf, Params())
    with pytest.raises(EngineFault):
        process(pdf, strict=True, registry=default_registry())


def test_processing_a_csv_needs_neither_a_pdf_library_nor_torch(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text(BANK, encoding="utf-8")
    code = ("import sys\nfrom decimal import Decimal\nfrom openbooks.core import process, Params\n"
            f"assert process({str(f)!r}, Params(currency='INR', opening=Decimal('1000')))['status'] == 'ok'\n"
            "print(sorted(m for m in ('torch', 'pypdfium2', 'easyocr', 'scipy', 'openbooks.gateways', 'openbooks.tax') if m in sys.modules))\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    assert out == "[]", out


def test_importing_the_model_assets_module_does_not_import_torch():
    code = "import sys, openbooks.statements.assets as a; print('torch' in sys.modules, a.MODELS_DIR.name)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.split()
    assert out[0] == "False"


def test_models_dir_can_be_overridden_by_the_environment(tmp_path):
    code = "from openbooks.statements.assets import MODELS_DIR; print(MODELS_DIR)"
    env = {**__import__("os").environ, "OPENBOOKS_MODELS_DIR": str(tmp_path)}
    assert subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env).stdout.strip() == str(tmp_path)


torch = pytest.importorskip("torch", reason="the typed heads need PyTorch (pip install 'openbooks[scan]')")


def test_calibration_that_does_not_match_the_weights_is_refused(tmp_path):
    from openbooks.core import Refusal
    from openbooks.statements.roles import RoleModel

    w, c = tmp_path / "w.pt", tmp_path / "c.json"
    w.write_bytes(b"not real weights")
    c.write_text(json.dumps({"weights_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(Refusal) as e:
        RoleModel.load(w, c)
    assert e.value.code == "UNSUPPORTED_INPUT" and "refit the calibration" in e.value.message
    head = {"temperature": 1, "qhat": 0.9, "alpha": 0.05}
    c.write_text(json.dumps({"weights_sha256": hashlib.sha256(b"not real weights").hexdigest(),
                             "role": head, "vtype": head}), encoding="utf-8")
    with pytest.raises(Refusal, match="Cannot load the model checkpoint") as e2:
        RoleModel.load(w, c)
    assert e2.value.code == "UNSUPPORTED_INPUT"


def test_the_shipped_weights_load_and_name_themselves():
    from openbooks.statements.assets import MODELS_DIR
    from openbooks.statements.roles import RoleModel

    if not (MODELS_DIR / "roles_head.pt").exists():
        pytest.skip("no model assets in this environment")
    ident = RoleModel.load().identity
    assert len(ident["weights_sha256"]) == 64 and len(ident["calibration_sha256"]) == 64
