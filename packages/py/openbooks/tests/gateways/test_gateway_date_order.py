from decimal import Decimal

from openbooks.core import Params, default_registry, process
from openbooks.core.process import _extract

WISE_HEAD = "TransferWise ID,Date,Amount,Currency,Description,Payment Reference,Running Balance,Total fees"
WISE_OK = [WISE_HEAD, "TRANSFER-1,05/01/2026,100.00,EUR,In,,1100.00,0.00", "CARD-2,13/01/2026,-25.50,EUR,Coffee,,1074.50,0.00"]
RAZORPAY_HEAD = "entity_id,type,debit,credit,amount,currency,fee,tax,created_at,settlement_id"
STRIPE_HEAD = "balance_transaction_id,created,currency,gross,fee,net,reporting_category"


def run(tmp_path, lines, **params):
    f = tmp_path / "in.csv"
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return process(f, Params(**{"opening": Decimal("1000.00"), **params}))


def wise(date_a, date_b):
    return [WISE_HEAD, f"TRANSFER-1,{date_a},100.00,EUR,In,,1100.00,0.00", f"CARD-2,{date_b},-25.50,EUR,Coffee,,1074.50,0.00"]


def test_wise_ambiguous_numeric_dates_refuse_instead_of_defaulting_to_day_first(tmp_path):
    doc = run(tmp_path, wise("03/04/2026", "04/04/2026"), currency="EUR")
    assert doc["error"]["code"] == "AMBIGUOUS_DATE"


def wise_evidence(tmp_path, lines, **params):
    f = tmp_path / "parse.csv"
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _, ev, *_ = _extract(f, Params(**{"currency": "EUR", "allow_derived_opening": True, **params}), default_registry(), lambda _name: None)
    return ev


def test_wise_file_proving_day_first_records_file_evidence(tmp_path):
    doc = run(tmp_path, WISE_OK, currency="EUR")
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"
    ev = wise_evidence(tmp_path, WISE_OK)
    assert ev["batch-1.date_order"]["raw_text"] == "dmy"
    assert ev["batch-1.date_order"]["provenance"] == "FILE_EVIDENCE"


def test_wise_declared_order_on_ambiguous_dates_is_caller_supplied_not_proof(tmp_path):
    lines = wise("03/04/2026", "04/04/2026")
    doc = run(tmp_path, lines, currency="EUR", date_order="mdy")
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"
    ev = wise_evidence(tmp_path, lines, date_order="mdy")
    assert ev["batch-1.date_order"]["raw_text"] == "mdy"
    assert ev["batch-1.date_order"]["provenance"] == "CALLER_SUPPLIED"


def test_wise_one_unambiguous_date_does_not_resolve_a_mixed_format_file(tmp_path):
    doc = run(tmp_path, wise("13/01/2026", "01/13/2026"), currency="EUR")
    assert doc["error"]["code"] == "PARSE_ERROR"


def test_wise_declared_order_contradicting_the_data_is_a_named_conflict(tmp_path):
    doc = run(tmp_path, wise("05/01/2026", "04/13/2026"), currency="EUR", date_order="dmy")
    assert doc["error"]["code"] == "PARSE_ERROR"
    assert "contradicts" in doc["error"]["message"]
    assert "unreadable" not in doc["error"]["message"]


def test_razorpay_ambiguous_created_dates_refuse(tmp_path):
    lines = [RAZORPAY_HEAD, "pay_1,payment,0.00,97.64,100.00,INR,2.00,0.36,05/01/2026 10:00:00,setl_1",
             "setl_1,settlement,77.64,0.00,77.64,INR,0.00,0.00,04/01/2026 10:00:00,setl_1"]
    doc = run(tmp_path, lines)
    assert doc["error"]["code"] == "AMBIGUOUS_DATE"


def test_stripe_ambiguous_created_dates_refuse(tmp_path):
    lines = [STRIPE_HEAD, "txn_1,05/01/2026 10:00,usd,100.00,3.20,96.80,charge",
             "po_1,04/01/2026 09:00,usd,-96.80,0.00,-96.80,payout"]
    doc = run(tmp_path, lines)
    assert doc["error"]["code"] == "AMBIGUOUS_DATE"


def test_stripe_declared_month_first_order_contradicted_by_data_refuses(tmp_path):
    lines = [STRIPE_HEAD, "txn_1,05/01/2026 10:00,usd,100.00,3.20,96.80,charge",
             "po_1,13/01/2026 09:00,usd,-96.80,0.00,-96.80,payout"]
    doc = run(tmp_path, lines, date_order="mdy")
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"
    assert "declared month-first order contradicts the data" in doc["error"]["message"]
