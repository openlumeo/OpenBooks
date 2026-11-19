"""openbooks.gateways with only openbooks.core registered: each layout releases, tampering refuses, providers stay isolated."""
import subprocess
import sys
from decimal import Decimal

import pytest

from openbooks.core import Params, default_registry, process

GATEWAYS = ("openbooks.gateways",)

STRIPE = """balance_transaction_id,created,currency,gross,fee,net,reporting_category
txn_1,2026-01-05 10:00:00,usd,100.00,3.20,96.80,charge
txn_2,2026-01-06 11:00:00,usd,50.00,1.75,48.25,charge
txn_3,2026-01-06 12:00:00,usd,-20.00,0.00,-20.00,refund
po_1,2026-01-07 09:00:00,usd,-125.05,0.00,-125.05,payout
"""
RAZORPAY = """entity_id,type,debit,credit,amount,currency,fee,tax,created_at,settlement_id
pay_1,payment,0.00,97.64,100.00,INR,2.00,0.36,2026-01-05 10:00:00,setl_1
rfnd_1,refund,20.00,0.00,20.00,INR,0.00,0.00,2026-01-06 10:00:00,setl_1
setl_1,settlement,77.64,0.00,77.64,INR,0.00,0.00,2026-01-07 10:00:00,setl_1
"""
PAYPAL = """Date,Time,TimeZone,Name,Type,Status,Currency,Gross,Fee,Net,From Email Address,To Email Address,Transaction ID,Balance Impact
01/15/2026,10:00:00,PST,Acme,Payment,Completed,USD,"1,100.00",-3.20,"1,096.80",a@x.com,b@y.com,T1,Credit
01/16/2026,11:00:00,PST,Acme,Authorization,Pending,USD,50.00,0.00,50.00,a@x.com,b@y.com,T2,Memo
02/03/2026,12:00:00,PST,Bob,Payment,Completed,USD,-50.00,0.00,-50.00,b@y.com,c@z.com,T3,Debit
"""
WISE = """TransferWise ID,Date,Amount,Currency,Description,Payment Reference,Running Balance,Total fees
CARD-3,13-01-2026,-25.50,EUR,Coffee,,1074.50,0.00
TRANSFER-2,02-01-2026,-100.00,EUR,Sent to Bob,rent,1100.00,0.50
TRANSFER-1,01-01-2026,200.00,EUR,Received from Ann,inv 1,1200.00,0.00
"""


@pytest.fixture
def run(tmp_path):
    def _run(text, **params):
        f = tmp_path / "in.csv"
        f.write_text(text, encoding="utf-8")
        return process(f, Params(**params))
    return _run


@pytest.mark.parametrize("text,layout,params", [
    (STRIPE, "stripe_balance.v1", {}), (RAZORPAY, "razorpay_settlement.v1", {}), (PAYPAL, "paypal_activity.v1", {}),
    (WISE, "wise_statement.v1", {"allow_derived_opening": True}),
])
def test_each_layout_releases_with_evidence_and_an_independent_assertion(run, text, layout, params):
    doc = run(text, **params)
    assert doc["status"] == "ok" and doc["file"]["layout_version"] == layout, doc.get("error")
    assert any(a["independent"] for a in doc["assertions"]) and all(a["passed"] for a in doc["assertions"])
    assert doc["evidence"]  # every amount and date has its raw text


@pytest.mark.parametrize("old,new", [("96.80", "96.81"), ("100.00", "100.01"), ("125.05", "125.06")])
def test_stripe_tampering_is_refused(run, old, new):
    doc = run(STRIPE.replace(old, new))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


@pytest.mark.parametrize("old,new", [("97.64", "97.65"), ("77.64", "77.65"), ("0.36", "0.37")])
def test_razorpay_tampering_is_refused(run, old, new):
    doc = run(RAZORPAY.replace(old, new))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_paypal_and_wise_tampering_is_refused(run):
    assert run(PAYPAL.replace("1,096.80", "1,096.81"))["error"]["code"] == "BALANCE_MISMATCH"
    assert run(WISE.replace("1074.50", "1074.51"), allow_derived_opening=True)["error"]["code"] == "BALANCE_MISMATCH"


def test_paypal_never_guesses_an_ambiguous_date_order(run):
    amb = PAYPAL.replace("01/15/2026", "01/05/2026").replace("01/16/2026", "01/06/2026")
    assert run(amb)["status"] == "refused"
    assert run(amb, date_order="mdy")["data"]["transactions"][0]["date"] == "2026-01-05"
    assert run(amb, date_order="dmy")["data"]["transactions"][0]["date"] == "2026-05-01"


def test_the_same_payment_gives_the_same_canonical_numbers_in_every_export(run):
    stripe = "balance_transaction_id,created,currency,gross,fee,net\nt1,2026-01-15 10:00:00,usd,100.00,3.20,96.80\n"
    razorpay = ("entity_id,type,debit,credit,amount,currency,fee,tax,created_at,settlement_id\n"
                "p1,payment,0.00,96.80,100.00,USD,3.20,0.00,2026-01-15 10:00:00,s1\n")
    paypal = ("Date,Time,TimeZone,Name,Type,Status,Currency,Gross,Fee,Net,Transaction ID,Balance Impact\n"
              "01/15/2026,10:00:00,PST,Acme,Payment,Completed,USD,100.00,-3.20,96.80,T1,Credit\n")
    seen = []
    for text in (stripe, razorpay, paypal):
        doc = run(text)
        assert doc["status"] == "ok", doc.get("error")
        t = doc["data"]["transactions"][0]
        seen.append({k: t[k] for k in ("date", "gross", "fee", "net")})
    assert seen[0] == seen[1] == seen[2] == {"date": "2026-01-15", "gross": {"amount": "100.00", "currency": "USD"},
                                             "fee": {"amount": "3.20", "currency": "USD"}, "net": {"amount": "96.80", "currency": "USD"}}


def test_amounts_are_decimal_strings_never_floats(run):
    for t in run(STRIPE)["data"]["transactions"]:
        assert isinstance(t["gross"]["amount"], str) and Decimal(t["gross"]["amount"]) == Decimal(t["gross"]["amount"])


def test_gateways_alone_refuse_a_bank_statement_and_name_the_package(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text("Date,Narration,Withdrawal Amt,Deposit Amt,Closing Balance\n01/01/2026,x,,5.00,1005.00\n", encoding="utf-8")
    doc = process(f, Params(currency="INR", opening=Decimal("1000")), registry=default_registry().restricted_to(GATEWAYS))
    assert doc["status"] == "refused" and "openbooks.statements" in doc["error"]["message"]


def test_processing_a_stripe_file_imports_no_other_provider(tmp_path):
    f = tmp_path / "in.csv"
    f.write_text(STRIPE, encoding="utf-8")
    code = ("import sys\nfrom openbooks.core import process\n"
            f"assert process({str(f)!r})['status'] == 'ok'\n"
            "print(sorted(m for m in sys.modules if '.'.join(m.split('.')[:2]) in ('openbooks.pipeline', 'openbooks.tax', 'openbooks.statements')))\n")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip().splitlines()[-1]
    assert out == "[]", out
