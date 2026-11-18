"""openbooks-tax with only openbooks-core: each layout releases only when the document proves itself, tampering refuses."""
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal

import pytest

from openbooks_core import Params, default_registry, process

TAX = ("openbooks-tax",)
TDS_HEAD = "Deductor Name,TAN,Section,Transaction Date,Amount Paid/Credited,Tax Deducted,TDS Deposited"
TDS_ROWS = ["Acme Ltd,MUMA12345B,194C,15/04/2025,100000.00,2000.00,2000.00",
            "Globex Pvt Ltd,DELG54321A,194J,20/05/2025,50000.50,5000.05,5000.05",
            "Initech,BLRI11111C,194C,01/06/2025,25000.00,500.00,500.00"]
TDS_TOTAL = "Total,,,,175000.50,7500.05,7500.05"
AIS_HEAD = "Information Category,Information Description,Source,Reported Value,Modified Value"
AIS_ROWS = ["Salary,Salary from Acme Ltd,Acme Ltd,1200000.00,1200000.00", "Interest,Savings interest,Some Bank,12345.67,12345.67",
            "Dividend,Dividend income,Some Co,4000.00,4000.00"]
AIS_TOTAL = "Total,,,1216345.67,"
FIRA_HEAD = "FIRA No,Date,Remitter,Currency,Foreign Amount,Exchange Rate,INR Amount,Bank Charges,Net Credited"
TB_HEAD = "Account,Debit,Credit"
TB_ROWS = ["Cash,5000.00,", "Receivables,3000.50,", "Payables,,2000.25", "Capital,,5000.00", "Revenue,,1000.25"]
B1099 = """Description,Date Acquired,Date Sold,Proceeds,Cost Basis,Wash Sale Loss Disallowed,Gain/Loss
100 sh ACME,01/15/2025,03/20/2026,1500.00,1000.00,,500.00
50 sh FOO,VARIOUS,04/21/2026,800.00,900.00,25.00,-75.00
TOTAL,,,2300.00,1900.00,,425.00
"""


def fira():
    rows, tot_inr, tot_net = [], Decimal(0), Decimal(0)
    for k, (fx, rate) in enumerate([("1000.00", "83.2150"), ("2500.50", "82.9000"), ("150.25", "83.1000")], 1):
        inr = (Decimal(fx) * Decimal(rate)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        rows.append(f"FIRA{k:03d},{k:02d}/05/2025,Remitter {k},USD,{fx},{rate},{inr},15.00,{inr - 15}")
        tot_inr += inr
        tot_net += inr - 15
    return rows, f"Total,,,,,,{tot_inr},,{tot_net}"


def csv(head, rows, total=None):
    return "\n".join([head] + rows + ([total] if total else [])) + "\n"


@pytest.fixture
def run(tmp_path):
    def _run(text, **params):
        f = tmp_path / "in.csv"
        f.write_text(text, encoding="utf-8")
        return process(f, Params(**params))
    return _run


def cases():
    fr, ft = fira()
    return [(csv(TDS_HEAD, TDS_ROWS, TDS_TOTAL), "tds_26as.v1", {}), (csv(AIS_HEAD, AIS_ROWS, AIS_TOTAL), "ais.v1", {}),
            (csv(FIRA_HEAD, fr, ft), "fira.v1", {}), (csv(TB_HEAD, TB_ROWS), "trial_balance.v1", {"currency": "INR"}),
            (B1099, "form_1099b.v1", {})]


@pytest.mark.parametrize("text,layout,params", cases())
def test_each_layout_releases_with_an_independent_assertion(run, text, layout, params):
    doc = run(text, **params)
    assert doc["status"] == "ok" and doc["file"]["layout_version"] == layout, doc.get("error")
    assert any(a["independent"] for a in doc["assertions"]) and all(a["passed"] for a in doc["assertions"])


@pytest.mark.parametrize("tampered", [
    csv(TDS_HEAD, TDS_ROWS, TDS_TOTAL.replace("7500.05,7500.05", "7500.06,7500.05")),
    csv(TDS_HEAD, [TDS_ROWS[0].replace("2000.00,2000.00", "2000.01,2000.00")] + TDS_ROWS[1:], TDS_TOTAL),
    csv(AIS_HEAD, AIS_ROWS, AIS_TOTAL.replace("1216345.67", "1216345.68")),
    csv(TB_HEAD, TB_ROWS[:-1] + ["Revenue,,1000.26"]),
    B1099.replace("425.00", "425.01"),
])
def test_a_cent_of_tampering_is_refused(run, tampered):
    doc = run(tampered, currency="INR")
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_a_document_with_no_printed_total_has_nothing_to_prove_itself_against(run):
    doc = run(csv(TDS_HEAD, TDS_ROWS))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_fira_fx_arithmetic_is_checked(run):
    rows, total = fira()
    doc = run(csv(FIRA_HEAD, [rows[0].replace("83215.00,15.00,83200.00", "83220.00,15.00,83205.00")] + rows[1:], total))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_1099b_refuses_a_date_order_it_cannot_prove(run):
    amb = B1099.replace("01/15/2025", "01/05/2025").replace("03/20/2026", "03/04/2026").replace("04/21/2026", "04/06/2026")
    assert run(amb)["status"] == "refused"
    assert run(amb, date_order="mdy")["status"] == "ok"


def test_the_default_currency_is_an_assumption_and_the_caller_can_override_it(run):
    assert run(csv(TDS_HEAD, TDS_ROWS, TDS_TOTAL))["data"]["batches"][0]["currency"] == "INR"
    assert run(B1099)["data"]["batches"][0]["currency"] == "USD"
    assert run(B1099, currency="EUR")["data"]["batches"][0]["currency"] == "EUR"


def test_tax_alone_refuses_a_stripe_file_and_names_the_package(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text("balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n", encoding="utf-8")
    doc = process(f, registry=default_registry().restricted_to(TAX))
    assert doc["status"] == "refused" and "openbooks-gateways" in doc["error"]["message"]


def test_processing_a_tax_file_imports_no_other_provider(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text(csv(TDS_HEAD, TDS_ROWS, TDS_TOTAL), encoding="utf-8")
    code = ("import sys\nfrom openbooks_core import process\n"
            f"assert process({str(f)!r})['status'] == 'ok'\n"
            "print(sorted(m for m in sys.modules if m.split('.')[0] in ('openbooks', 'openbooks_gateways', 'openbooks_statements')))\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    assert out == "[]", out
