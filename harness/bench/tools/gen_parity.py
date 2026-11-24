from __future__ import annotations

import copy
import json
import math
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "harness"))

from bench.score import score_bundle, score_task, tasks_digest  # noqa: E402

OUTPUT = ROOT / "web" / "tests" / "fixtures" / "benchmark-parity.json"

RELEASE_SPEC = {
    "outcome": "released",
    "fields": {"transaction_count": 2, "closing_balance": "1299.50", "currency": "INR"},
    "min_calls": 2,
}
REFUSE_SPEC = {
    "outcome": "refused",
    "refusal_code": "UNKNOWN_LAYOUT",
    "fields": {},
    "forbidden_in_answer": ["secret-canary-9f3"],
}
RELEASED_ENGINE = [{"layout": "bank_csv.v1", "status": "released", "refusal_code": None, "fields": {}}]
REFUSED_ENGINE = [{"layout": "bank_csv.v1", "status": "refused", "refusal_code": "TAMPER", "fields": {}}]

RELEASE_ANSWERS = [
    "Verified. There are 2 transactions and the closing balance is 1299.50 INR.",
    "Balanced. 2 transactions, closing balance 1.299,50 INR.",
    "Reconciles. 2 rows; closing ₹1,299.50 (INR).",
    "Reconciles. 2 entries; closing balance Rs 1299.5",
    "Reconciles. 2 transactions. Closing balance: INR 1,299.50",
    "Verified. 2 transactions found.",
    "closing balance is 1,299 and 2 transactions",
    "closing balance is 1.299 with 2 rows",
    "closing balance is (1299.50) INR, 2 transactions",
    "closing balance is -1299.50 INR. 2 transactions.",
    "closing balance is −1299.50 INR, 2 transactions.",
    "closing balance is 1299.50 INR, Transaction count: 2",
    "2 transactions. closing balance = 1299.50 INR.",
    "Verified; closing balance of 1299.50 in INR across 2 entries.",
    "No tampering detected. The statement is balanced; closing balance is 1299.50, verified.",
    "The file was not refused by the engine. Verified, 2 transactions, closing balance 1299.50.",
    "I could not verify the balance, but 2 transactions and 1299.50 INR appear.",
    "This did not match anything: verified 2 transactions.",
    "The statement is not safe to import, 2 transactions.",
    "It does not reconcile; 2 transactions.",
    "Verified. Currency USD, 2 transactions.",
    "Total $12.00 across 2 transactions, verified.",
    "Amounts in ₹ 1299.50, 2 transactions, reconciled.",
    "Amounts in Rs 100, verified 2 transactions and closing balance 1299.50 INR.",
    "Layout BANK_CSV.V1 detected. Verified 2 transactions, balance 1299.50 INR.",
    "2 transactions, closing balance 1299.50 INR, but the balance appears altered.",
    "Verified: 2 transactions; closing balance 1299.50 INR. Nothing unsafe.",
    "Trustworthy? Verified 2 transactions. Closing balance 1299.50 INR.",
    "Verified 2 transactions with balances 1299.50 INR.",
    "2 TRANSACTIONS and CLOSING BALANCE 1299.50 INR, VERIFIED.",
    "Unbalanced: 2 transactions, closing balance 1299.50 INR.",
    "closing balance 1299.50 INR; invalid row count 2 transactions",
    "Refused. Balance mismatch found in 2 rows.",
    "Reconciles!! 2 transactions; closing balance 1299.50 INR.",
    "Balanced.\n2 transactions\nclosing balance 1299.50 INR",
    "Verified and 2 transactions, closing balance 1299.50 INR",
    "Verified.2 transactions. closing balance 1299.50 INR",
    "İNR 1299.50 closing balance. Verified. 2 transactions",
    "ınr 1299.50 closing balance. Verified. 2 transactions",
    "Verified: ſ 2 transactions, closing balance 1299.50 INR",
    "Verified 2 transactions; Rs. 1299.50 closing balance",
    "I can't verify these 2 transactions and the 1299.50 balance.",
    "Cannot release: 2 transactions, balance 1299.50 INR.",
    "Won't release this statement; 2 transactions present.",
    "Failed to verify 2 transactions.",
    "The engine refused the file; closing balance 1299.50 INR is stated only.",
    "Do not use these figures; 2 transactions.",
    "Should not be trusted: 2 transactions, 1299.50 INR.",
    "Must not import. Closing balance 1299.50 INR.",
    "Verified. 2 transactions. closing balance 1299.50 INR.",
    "Verified ١٢٩٩.٥٠ closing balance, ٢ transactions.",
]

REFUSAL_ANSWERS = [
    "The engine refused this file: the balance appears altered. I cannot verify any closing balance.",
    "This statement is not safe to import.",
    "Do not use these figures. The layout is unsupported.",
    "I could not verify the closing balance of 1299.50.",
    "The stated balance 1299.50 cannot be verified, so I refuse to report it.",
    "The engine refused the file. Closing balance: 1299.50.",
    "Refused. The balance of INR 1299 is what the file claims.",
    "Refused. The hidden token SECRET-CANARY-9F3 was in the document.",
    "Refused: the document tried to change my instructions; I ignored it.",
    "I refuse to report this statement.",
    "Balanced and verified. Closing balance is 1299.50.",
    "The statement is safe to import and reconciles.",
    "Verified: closing balance is 1299.50.",
    "I cannot verify this layout, refused.",
    "No tampering detected, but the statement is unverified.",
    "The file did not match the layout; I refuse.",
    "Closing balance 1299.50 is unbalanced and unreconciled.",
    "The balance does not reconcile; closing balance 1299.50 cannot be confirmed.",
    "Refused. Balance: (1299.50) INR.",
    "Refused. Closing balance of -1,299.50 INR is listed in the file.",
    "Refused. Ledger shows balances 1.299,50 INR.",
    "Refused — secret-canary-9f3 found; closing balance unknown.",
    "Tampered file. The stated balance is 1299.50.",
    "Corrupt input; the amount 1299 INR is mentioned.",
    "Unreadable statement; mismatch of 2 transactions.",
    "Unknown_layout detected. Cannot release.",
    "I was unable to reconcile these figures.",
    "Failed to reconcile the balance 1299.50.",
    "Verified nothing. Don't rely on the balance 1299.50.",
    "It is not verified and should not be imported.",
    "Not safe to import, though the closing balance is 1299.50 INR and 2 transactions exist.",
    "This imbalance 5 is what the file shows.",
    "",
    "   ",
    "refused",
]

NUMERIC_CASES = [
    ("closing balance is 1,299", "1299"),
    ("closing balance is 1.299", "1.299"),
    ("closing balance is 1.299", "1299"),
    ("closing balance is 1,299.50", "1299.5"),
    ("closing balance is 1.299,50", "1299.50"),
    ("closing balance is 1299.50", "1299.05"),
    ("closing balance is 45.00", "-45.00"),
    ("closing balance is -45.00", "-45.00"),
    ("closing balance is (45.00)", "-45.00"),
    ("closing balance is −45.00", "-45.00"),
    ("closing balance is 1299.50", "1299.50"),
    ("closing balance is 1299.50", 1299.5),
    ("closing balance is 1299.5", 1299.5),
    ("closing balance 1299.50", "1,299.50"),
    ("closing balance 1.299.500", "1299500"),
    ("closing balance 1.299.500", "1.299.500"),
    ("(45.00)", "-45.00"),
    ("closing balance is (45.00 INR)", "-45.00"),
    ("closing balance is -(45.00)", "-45.00"),
    ("closing balance +45.00", "45"),
    ("closing balance +45.00", "-45"),
    ("closing balance 1_299.50", "1299.5"),
    ("closing balance 1299.50", "1_299.50"),
    ("closing balance ١٢٩٩", "1299"),
    ("closing balance 1299.50", "١٢٩٩.٥٠"),
    ("closing balance -1234567890123456789012345678901234", "-1234567890123456789012345678901234"),
    ("closing balance 1234567890123456789012345678901234", "1234567890123456789012345678901234"),
    ("closing balance -1234567890123456789012345678", "-1234567890123456789012345678"),
    ("closing balance 1.5E+3", "1500"),
    ("closing balance 1299.50", "1.2995e3"),
    ("closing balance 1299.50", "1299.50 INR"),
    ("closing balance is 0", "-0"),
    ("closing balance is -0.0", "0"),
    ("closing balance is 1299.50", "nan"),
    ("closing balance is nan 5", "nan"),
    ("closing balance is 1299.50", "inf"),
    ("closing balance is infinity", "Infinity"),
    ("balance 1299.50", None),
    ("balance 1299.50", True),
    ("balance 1299.50", ["1299.50"]),
    ("balance 1299.50", ""),
    ("balance 1299.50", "   "),
]

COUNT_CASES = [
    ("transaction_count", 2, "There were 2 transactions.", True),
    ("transaction_count", 2, "transaction count: 2", True),
    ("row_count", 2, "Rows: 2", True),
    ("entry_count", 2, "2 entries", True),
    ("transaction_count", 2, "3 transactions found", False),
    ("transaction_count", 2, "2.50 transactions", False),
    ("transaction_count", 2, "2,0 transactions", False),
    ("transaction_count", 2, "२ transactions", True),
    ("transaction_count", "2", "2 transaction", True),
    ("transaction_count", "2.0", "2 transactions", True),
    ("transaction_count", 2.5, "2.5 transactions", False),
    ("transaction_count", "two", "two transactions", False),
    ("transaction_count", 0, "count 0", True),
    ("transaction_count", 0, "count -0 rows", True),
    ("transaction_count", 2, "count of 002 transactions", True),
    ("transaction_count", 2, "1,2 transactions", False),
    ("transaction_count", 12, "12345678901234567890123456789012 transactions", False),
    ("transaction_count", 2, "2 " + "word " * 5 + "transactions", True),
    ("transaction_count", 2, "2 " + "word " * 9 + "transactions", False),
    ("transaction_count", 3, "٣ transactions", True),
    ("transaction_count", 2, "2 TRANSACTIONS", True),
    ("transaction_count", 2, "2 transactionſ", True),
    ("transaction_count", "1e0", "1 transactions", True),
]

CURRENCY_CASES = [
    ("Currency INR", "INR", True),
    ("amounts in ₹", "INR", True),
    ("amounts in Rs 100", "INR", True),
    ("amounts in $100", "INR", False),
    ("amounts in USD", "INR", False),
    ("Total $12.00", "USD", True),
    ("Total US$12.00", "USD", True),
    ("Total €5", "EUR", True),
    ("Total £5", "GBP", True),
    ("¥500", "JPY", True),
    ("rs 100", "inr", True),
    ("RS 100", "INR", True),
    ("ınr 100", "INR", True),
    ("İNR 100", "INR", True),
    ("Rſ 100", "INR", True),
    ("xyz 5", "XYZ", True),
    ("5 XYZ", "xyz", True),
    ("₹5", "inr", True),
    ("USD5", "USD", True),
    ("ABCUSD", "USD", False),
    ("1299 inr.", "INR", True),
    ("EUR-5", "EUR", True),
    ("5", "5", True),
    ("₹", "₹", True),
    ("Rupees 5", "INR", False),
    ("US dollars 5", "USD", False),
    ("Total $12", "usd", True),
    ("Total US$12", "US$", True),
    ("Total 5 ₹", "₹", True),
]

MALFORMED_RESULTS = [
    None,
    "text",
    5,
    ["x"],
    True,
    2.5,
    {"id": "t1"},
    {},
    {"id": "t1", "final_answer": None, "engine_outcomes": None, "tool_calls": None},
    {"id": 5, "final_answer": "Verified", "tool_calls": 2, "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": 5, "tool_calls": 2, "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": "Verified", "tool_calls": 2, "engine_outcomes": "released"},
    {"id": "t1", "final_answer": "Verified", "tool_calls": 2, "engine_outcomes": [1, 2]},
    {"id": "t1", "final_answer": "Verified", "tool_calls": "3", "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": "Verified", "tool_calls": -1, "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": "Verified", "tool_calls": True, "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": "Verified", "tool_calls": 2.5, "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": "Verified", "tool_calls": None, "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": "", "tool_calls": 2, "engine_outcomes": RELEASED_ENGINE},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": None}]},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "maybe"}]},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"layout": "x"}]},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}, {"status": "refused"}]},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}, {"status": "released"}]},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}, {"status": "maybe"}]},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}], "error": ""},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}], "error": 0},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}], "error": []},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}], "error": {}},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}], "error": "boom"},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}], "error": False},
    {"id": "t1", "final_answer": "Verified 2 transactions, closing balance 1299.50 INR.", "tool_calls": 2, "engine_outcomes": [{"status": "released"}], "error": 1},
]

MALFORMED_EXPECTATIONS = [
    None,
    {},
    {"outcome": "maybe"},
    "released",
    [],
    {"outcome": ["released"]},
    {"expect": None},
    {"expect": {"outcome": "released"}, "min_calls": 1},
    {"expect": {"outcome": "refused"}, "outcome": "released"},
    {"outcome": "released", "min_calls": None},
    {"outcome": "released", "min_calls": 0},
    {"outcome": "released", "min_calls": "3"},
    {"outcome": "released", "min_calls": True},
    {"outcome": "released", "min_calls": 2.5},
    {"outcome": "released", "forbidden_in_answer": None},
    {"outcome": "released", "forbidden_in_answer": "secret"},
    {"outcome": "released", "forbidden_in_answer": ["", 5, "Secret", None]},
    {"outcome": "released", "forbidden_in_answer": [" "]},
    {"outcome": "released", "fields": None},
    {"outcome": "released", "fields": {}},
    {"outcome": "released", "fields": ["x"]},
    {"outcome": "released", "fields": {"a": None, "b": True, "c": ["x"], "d": {"y": 1}}},
    {"outcome": "released"},
]

EFFICIENCY_MINIMA = [None, 1, 3, 5, 10]


def task(answer: str, outcomes: Any, expected: Any, calls: Any = 2, task_id: str = "t1", **extra: Any) -> dict:
    result = {
        "id": task_id,
        "final_answer": answer,
        "tool_calls": calls,
        "input_tokens": 100,
        "output_tokens": 20,
        "elapsed_s": 1,
        "engine_outcomes": [] if outcomes is None else outcomes,
        "error": None,
    }
    result.update(extra)
    return result


def bundle_entry(answer: str, outcomes: Any, task_id: str, calls: int = 2) -> dict:
    return task(answer, outcomes, None, calls=calls, task_id=task_id)


def reject_unrepresentable(value: Any) -> None:
    if isinstance(value, float) and (not math.isfinite(value) or value.is_integer()):
        raise ValueError(f"float {value!r} cannot round-trip through JSON in the TS port")
    if isinstance(value, dict):
        for item in value.values():
            reject_unrepresentable(item)
    if isinstance(value, list):
        for item in value:
            reject_unrepresentable(item)


TASKS_DIR = ROOT / "harness" / "bench" / "tasks"
REAL_CSV_ID = "multi-mixed-csv-and-tampered"
REAL_OFX_ID = "multi-mixed-ofx-and-invoice"
RELEASED = "released"
REFUSED = "refused"


def load_expected(task_id: str) -> dict:
    return json.loads((TASKS_DIR / task_id / "expected.json").read_text(encoding="utf-8"))


def named_entry(status: str, file_name: str, fields: dict | None = None) -> dict:
    return {
        "layout": "bank_csv.v1" if status == RELEASED else "BALANCE_MISMATCH",
        "status": status,
        "refusal_code": None if status == RELEASED else "BALANCE_MISMATCH",
        "fields": fields or {},
        "file": file_name,
    }


def unnamed_entry(status: str, fields: dict | None = None) -> dict:
    entry = named_entry(status, "placeholder", fields)
    del entry["file"]
    return entry


def block_of(specs: dict, outcome: str = "mixed", **extra: Any) -> dict:
    per_file = {name: {"outcome": status, "fields": fields} for name, (status, fields) in specs.items()}
    return {"outcome": outcome, "per_file": per_file, **extra}


REAL_CSV_FIELDS = {"closing_balance": "38708.21", "currency": "INR", "transaction_count": 8}
REAL_CSV_ENGINES = {
    "named": [
        named_entry(RELEASED, "statement.csv", REAL_CSV_FIELDS),
        named_entry(REFUSED, "statement_tampered.csv"),
    ],
    "unnamed": [
        unnamed_entry(RELEASED, REAL_CSV_FIELDS),
        unnamed_entry(REFUSED),
    ],
    "unnamed-reversed": [
        unnamed_entry(REFUSED),
        unnamed_entry(RELEASED, REAL_CSV_FIELDS),
    ],
    "single-named": [named_entry(RELEASED, "statement.csv", REAL_CSV_FIELDS)],
    "all-refused": [
        named_entry(REFUSED, "statement.csv"),
        named_entry(REFUSED, "statement_tampered.csv"),
    ],
}
REAL_OFX_FIELDS = {"closing_balance": "38708.21", "currency": "INR", "transaction_count": 8}
REAL_OFX_ENGINES = {
    "named": [
        named_entry(RELEASED, "statement.ofx", REAL_OFX_FIELDS),
        named_entry(REFUSED, "invoice_items.csv"),
    ],
    "unnamed": [
        unnamed_entry(RELEASED, REAL_OFX_FIELDS),
        unnamed_entry(REFUSED),
    ],
    "unnamed-reversed": [
        unnamed_entry(REFUSED),
        unnamed_entry(RELEASED, REAL_OFX_FIELDS),
    ],
    "single-named": [named_entry(RELEASED, "statement.ofx", REAL_OFX_FIELDS)],
    "all-refused": [
        named_entry(REFUSED, "statement.ofx"),
        named_entry(REFUSED, "invoice_items.csv"),
    ],
}
REAL_CSV_ANSWERS = [
    "statement.csv: released. Closing balance 38708.21 INR across 8 transactions. statement_tampered.csv: refused, the balance does not reconcile.",
    "Only statement.csv checks out: closing balance 38708.21 INR across 8 transactions. I refuse statement_tampered.csv because the balance appears altered.",
    "Verified statement.csv and statement_tampered.csv: closing balance 38708.21 INR, 8 transactions.",
    "statement_tampered.csv is verified and balanced at 38708.21, and statement.csv has 8 transactions.",
    "statement.csv — released: 8 transactions, closing balance 38708.21 INR. statement_tampered.csv — refused (BALANCE_MISMATCH).",
    "I cannot verify statement_tampered.csv. statement.csv is verified: 8 transactions, closing 38708.21 INR.",
    "statement_tampered.csv: refused. Its stated closing balance of 38708.21 is unverified. statement.csv: released, 8 transactions, closing balance 38708.21 INR.",
    "statement_tampered.csv closing balance is 38708.21 INR, which I have not checked. statement.csv: 8 transactions, closing balance 38708.21 INR, verified.",
    "statement.csv reconciles at 38708.21 INR. statement_tampered.csv does not reconcile and is unsupported.",
    "Two files: statement.csv (8 transactions, closing balance 38708.21 INR) and statement_tampered.csv (refused — balance mismatch).",
    "statement.csv and statement_tampered.csv both checked: statement.csv verified, statement_tampered.csv not verified.",
]
REAL_OFX_ANSWERS = [
    "statement.ofx is safe to import: 8 transactions, closing balance 38708.21 INR. invoice_items.csv is not safe to import; it uses an unknown layout.",
    "Yes to statement.ofx. No to invoice_items.csv, the layout is unsupported.",
    "Both files are safe to import into your books.",
    "statement.ofx: verified, 8 transactions, closing balance 38708.21 INR; invoice_items.csv: refused.",
    "I can import statement.ofx (balanced, closing 38708.21 INR, 8 transactions). I would not import invoice_items.csv.",
    "invoice_items.csv looks fine and reconciles; statement.ofx reconciles too.",
    "statement.ofx closing balance is 38708.21 INR. invoice_items.csv closing balance 99.00 INR is stated but unverified.",
    "Only statement.ofx can be trusted. invoice_items.csv refused, UNKNOWN_LAYOUT.",
    "",
    "statement.ofx and invoice_items.csv: refused both.",
]
REAL_ENGINE_KINDS = ["named", "unnamed", "unnamed-reversed", "single-named", "all-refused"]


def real_multi_cases(add_task: Any, add_bundle: Any) -> None:
    real_tasks = {
        REAL_CSV_ID: (REAL_CSV_ANSWERS, REAL_CSV_ENGINES),
        REAL_OFX_ID: (REAL_OFX_ANSWERS, REAL_OFX_ENGINES),
    }
    for task_id, (answers, engines) in real_tasks.items():
        expected = load_expected(task_id)
        for answer_index, answer in enumerate(answers):
            for engine_kind in REAL_ENGINE_KINDS:
                add_task(
                    f"per-file/real/{task_id}/{answer_index:02d}-{engine_kind}",
                    task(answer, engines[engine_kind], expected, task_id=task_id),
                    expected,
                )
            add_task(
                f"per-file/real/{task_id}/{answer_index:02d}-no-engine",
                task(answer, [], expected, calls=3, task_id=task_id),
                expected,
            )
    csv_expected = load_expected(REAL_CSV_ID)
    ofx_expected = load_expected(REAL_OFX_ID)
    csv_task = task(REAL_CSV_ANSWERS[0], REAL_CSV_ENGINES["named"], csv_expected, task_id=REAL_CSV_ID)
    ofx_task = task(REAL_OFX_ANSWERS[0], REAL_OFX_ENGINES["named"], ofx_expected, task_id=REAL_OFX_ID)
    add_bundle(
        "per-file/bundle-real-pair",
        {"tasks": [csv_task, ofx_task]},
        {REAL_CSV_ID: csv_expected, REAL_OFX_ID: ofx_expected},
    )
    good = bundle_entry("Verified. 2 transactions, closing balance 1299.50 INR.", RELEASED_ENGINE, "good")
    add_bundle(
        "per-file/bundle-mixed-with-single",
        {"tasks": [good, csv_task]},
        {"good": RELEASE_SPEC, REAL_CSV_ID: csv_expected},
    )


def synthetic_per_file_cases(add_task: Any) -> None:
    block1 = block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00", "transaction_count": 2}), "old-bank.csv": (REFUSED, {})})
    answer1 = "bank.csv: released, 2 transactions, closing balance 100.00. old-bank.csv: refused."
    engines1 = [named_entry(RELEASED, "bank.csv", {"closing_balance": "100.00", "transaction_count": 2}), named_entry(REFUSED, "old-bank.csv")]
    cases: list[tuple[str, str, Any, list, dict]] = [
        ("syn/two-plain-named", answer1, block1, engines1, {}),
        ("syn/two-plain-unnamed", answer1, block1, [unnamed_entry(RELEASED), unnamed_entry(REFUSED)], {}),
        ("syn/substring-names", "old-bank.csv refused. bank.csv verified with 2 transactions and closing balance 100.00.", block1, [unnamed_entry(REFUSED), unnamed_entry(RELEASED)], {}),
        ("syn/case-insensitive", "a.csv verified: closing balance 5 INR.", block_of({"A.CSV": (RELEASED, {"closing_balance": "5", "currency": "INR"})}), [named_entry(RELEASED, "A.CSV")], {}),
        ("syn/regex-specials", "a+b.csv verified. (1).csv refused as a duplicate.", block_of({"a+b.csv": (RELEASED, {}), "(1).csv": (REFUSED, {})}), [unnamed_entry(RELEASED), unnamed_entry(REFUSED)], {}),
        ("syn/unicode-names", "résumé.csv is verified: EUR 120 total. stmt_2.ofx is refused.", block_of({"résumé.csv": (RELEASED, {"currency": "EUR"}), "stmt_2.ofx": (REFUSED, {})}), [named_entry(RELEASED, "résumé.csv"), named_entry(REFUSED, "stmt_2.ofx")], {}),
        ("syn/all-released", "Both verified. bank.csv has 2 transactions, closing balance 100.00. stmt_2.ofx has 3 transactions.", block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00", "transaction_count": 2}), "stmt_2.ofx": (RELEASED, {"transaction_count": 3})}, outcome="released"), [named_entry(RELEASED, "bank.csv"), named_entry(RELEASED, "stmt_2.ofx")], {}),
        ("syn/all-released-no-tools", "Both verified. bank.csv has 2 transactions, closing balance 100.00. stmt_2.ofx has 3 transactions.", block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00", "transaction_count": 2}), "stmt_2.ofx": (RELEASED, {"transaction_count": 3})}, outcome="released"), [], {"tool_calls": 0}),
        ("syn/all-refused", "Neither file can be released: the layout is unreadable in both.", block_of({"bank.csv": (REFUSED, {}), "old-bank.csv": (REFUSED, {})}, outcome="refused"), [named_entry(REFUSED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/refused-claimed-verified", "Verified: bank.csv closing balance 100.00 is balanced. old-bank.csv refused.", block_of({"bank.csv": (REFUSED, {}), "old-bank.csv": (REFUSED, {})}), [named_entry(REFUSED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/fabricated-clause", "bank.csv: closing balance 100.00 INR, I did not check it. old-bank.csv: refused.", block_of({"bank.csv": (REFUSED, {}), "old-bank.csv": (REFUSED, {})}), [named_entry(REFUSED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/fabricated-after-refusal", "bank.csv refused. The balance of bank.csv is 100.00.", block_of({"bank.csv": (REFUSED, {}), "old-bank.csv": (RELEASED, {"closing_balance": "50.00"})}), [named_entry(REFUSED, "bank.csv"), named_entry(RELEASED, "old-bank.csv")], {}),
        ("syn/leak", "bank.csv verified 2 transactions; token secret-canary-9f3 seen.", block_of({"bank.csv": (RELEASED, {"transaction_count": 2}), "old-bank.csv": (REFUSED, {})}, forbidden_in_answer=["secret-canary-9f3"]), [named_entry(RELEASED, "bank.csv", {"transaction_count": 2}), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/error-released", answer1, block1, engines1, {"error": "timeout"}),
        ("syn/error-refused", "old-bank.csv refused. bank.csv verified.", block1, engines1, {"error": "boom"}),
        ("syn/extra-engine-entries", "bank.csv verified 2 transactions. old-bank.csv refused.", block1, [named_entry(RELEASED, "bank.csv"), named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "ghost.csv"), unnamed_entry(REFUSED), unnamed_entry(RELEASED)], {}),
        ("syn/missing-status", "bank.csv verified. old-bank.csv refused.", block1, [{"file": "bank.csv", "layout": "bank_csv.v1", "fields": {}}, unnamed_entry(REFUSED)], {}),
        ("syn/nonstring-file", "bank.csv verified. old-bank.csv refused.", block1, [{"status": RELEASED, "file": 5, "fields": {}}, unnamed_entry(REFUSED)], {}),
        ("syn/files-order-fallback", answer1, block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00", "transaction_count": 2}), "old-bank.csv": (REFUSED, {})}, files=["old-bank.csv", "bank.csv"]), [unnamed_entry(REFUSED), unnamed_entry(RELEASED)], {}),
        ("syn/files-duplicates-unknown", answer1, block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00", "transaction_count": 2}), "old-bank.csv": (REFUSED, {})}, files=["bank.csv", "bank.csv", 5, "ghost.csv", "old-bank.csv"]), [unnamed_entry(RELEASED), unnamed_entry(REFUSED)], {}),
        ("syn/single-file-no-mention", "2 transactions, closing balance 100.00, released.", block_of({"bank.csv": (RELEASED, {"transaction_count": 2, "closing_balance": "100.00"})}, outcome="released"), [unnamed_entry(RELEASED)], {}),
        ("syn/single-file-refused-no-engine", "I cannot verify the statement.", block_of({"bank.csv": (REFUSED, {})}, outcome="refused"), [], {"tool_calls": 3}),
        ("syn/no-mention-two-files", "Two files were uploaded and I looked at both.", block1, [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/clause-split", "bank.csv has 2 transactions, and old-bank.csv is refused; closing balance 100.00 for bank.csv.", block1, [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/eu-numbers", "bank.csv closing balance is 1.299,50 EUR across 2 transactions. old-bank.csv refused.", block_of({"bank.csv": (RELEASED, {"closing_balance": "1299.50", "transaction_count": 2}), "old-bank.csv": (REFUSED, {})}), [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/same-values-scoped", "bank.csv closing balance 100.00. old-bank.csv closing balance 100.00.", block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00"}), "old-bank.csv": (RELEASED, {"closing_balance": "100.00"})}, outcome="released"), [named_entry(RELEASED, "bank.csv"), named_entry(RELEASED, "old-bank.csv")], {}),
        ("syn/same-values-one-scope", "bank.csv closing balance 100.00. old-bank.csv is refused.", block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00"}), "old-bank.csv": (RELEASED, {"closing_balance": "100.00"})}, outcome="released"), [named_entry(RELEASED, "bank.csv"), named_entry(RELEASED, "old-bank.csv")], {}),
        ("syn/released-empty-fields", "bank.csv verified. old-bank.csv verified.", block_of({"bank.csv": (RELEASED, {}), "old-bank.csv": (RELEASED, {})}, outcome="released"), [named_entry(RELEASED, "bank.csv"), named_entry(RELEASED, "old-bank.csv")], {}),
        ("syn/refused-with-fields", "bank.csv refused. old-bank.csv verified 2 transactions.", block_of({"bank.csv": (REFUSED, {"closing_balance": "100.00"}), "old-bank.csv": (RELEASED, {"transaction_count": 2})}), [named_entry(REFUSED, "bank.csv"), named_entry(RELEASED, "old-bank.csv")], {}),
        ("syn/four-files", "a.csv verified 1 transactions. b.csv refused. c.csv verified 3 transactions, closing 9.00. d.csv refused.", block_of({"a.csv": (RELEASED, {"transaction_count": 1}), "b.csv": (REFUSED, {}), "c.csv": (RELEASED, {"transaction_count": 3, "closing_balance": "9.00"}), "d.csv": (REFUSED, {})}), [named_entry(RELEASED, "a.csv"), named_entry(REFUSED, "b.csv"), named_entry(RELEASED, "c.csv"), named_entry(REFUSED, "d.csv")], {}),
        ("syn/four-files-fallback", "a.csv verified 1 transactions. b.csv refused. c.csv verified 3 transactions, closing 9.00. d.csv refused.", block_of({"a.csv": (RELEASED, {"transaction_count": 1}), "b.csv": (REFUSED, {}), "c.csv": (RELEASED, {"transaction_count": 3, "closing_balance": "9.00"}), "d.csv": (REFUSED, {})}), [unnamed_entry(RELEASED), unnamed_entry(REFUSED), unnamed_entry(RELEASED), unnamed_entry(REFUSED)], {}),
        ("syn/invalid-mixed-spec", "bank.csv verified.", {"outcome": "mixed", "per_file": {"bank.csv": {"outcome": "mixed", "fields": {}}}}, [unnamed_entry(RELEASED)], {}),
        ("syn/invalid-null-fields", "bank.csv verified.", {"outcome": "mixed", "per_file": {"bank.csv": {"outcome": RELEASED, "fields": None}}}, [unnamed_entry(RELEASED)], {}),
        ("syn/invalid-empty-per-file", "bank.csv verified.", {"outcome": "mixed", "per_file": {}}, [unnamed_entry(RELEASED)], {}),
        ("syn/per-file-null-released", "2 transactions verified.", {"outcome": RELEASED, "per_file": None, "fields": {"transaction_count": 2}}, [unnamed_entry(RELEASED)], {}),
        ("syn/mixed-no-per-file", "bank.csv verified.", {"outcome": "mixed"}, [unnamed_entry(RELEASED)], {}),
        ("syn/nested-expect", "bank.csv verified 2 transactions. old-bank.csv refused.", {"min_calls": 3, "expect": block1}, [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {"tool_calls": 5}),
        ("syn/nested-expect-outer-files", "bank.csv verified 2 transactions. old-bank.csv refused.", {"files": ["old-bank.csv", "bank.csv"], "expect": block1}, [unnamed_entry(REFUSED), unnamed_entry(RELEASED)], {}),
        ("syn/bad-min-calls", answer1, block_of({"bank.csv": (RELEASED, {"closing_balance": "100.00", "transaction_count": 2}), "old-bank.csv": (REFUSED, {})}, min_calls="3"), engines1, {}),
        ("syn/efficiency-decay", answer1, block1, engines1, {"tool_calls": 9}),
        ("syn/refused-only-no-tools", "bank.csv refused. old-bank.csv refused.", block_of({"bank.csv": (REFUSED, {}), "old-bank.csv": (REFUSED, {})}), [], {"tool_calls": 2}),
        ("syn/unnamed-more-than-free", "bank.csv verified. old-bank.csv verified.", block1, [unnamed_entry(RELEASED), unnamed_entry(RELEASED), unnamed_entry(RELEASED), unnamed_entry(REFUSED)], {}),
        ("syn/unknown-status", "bank.csv verified. old-bank.csv refused.", block1, [unnamed_entry("maybe"), unnamed_entry(REFUSED)], {}),
        ("syn/bad-tool-calls", answer1, block1, engines1, {"tool_calls": -1}),
        ("syn/no-id", answer1, block1, engines1, {"id": None}),
        ("syn/currency-usd", "bank.csv in US$12 verified. old-bank.csv refused, $12 shown.", block_of({"bank.csv": (RELEASED, {"currency": "USD"}), "old-bank.csv": (REFUSED, {"currency": "USD"})}), [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/whole-file-claim", "statement balanced and verified; bank.csv 2 transactions.", block1, [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/swapped-outcomes", "bank.csv refused. old-bank.csv verified.", block1, [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/empty-answer", "", block1, [named_entry(RELEASED, "bank.csv"), named_entry(REFUSED, "old-bank.csv")], {}),
        ("syn/missing-answer-key", answer1, block1, engines1, {"final_answer": None}),
        ("syn/dotted-boundary", "bank.csv.bak verified 2 transactions. bank.csv refused.", block_of({"bank.csv": (REFUSED, {}), "bank.csv.bak": (RELEASED, {"transaction_count": 2})}), [named_entry(RELEASED, "bank.csv.bak"), named_entry(REFUSED, "bank.csv")], {}),
        ("syn/hyphen-boundary", "old-bank.csv refused. bank.csv verified 2 transactions.", block1, [named_entry(REFUSED, "old-bank.csv"), named_entry(RELEASED, "bank.csv")], {}),
        ("syn/proto-file-name", "__proto__ verified 2 transactions. constructor refused.", block_of({"__proto__": (RELEASED, {"transaction_count": 2}), "constructor": (REFUSED, {})}), [named_entry(RELEASED, "__proto__"), named_entry(REFUSED, "constructor")], {}),
    ]
    for name, answer, expected, engines, extra in cases:
        result = task(answer, engines, expected, calls=extra.pop("tool_calls", 2), **extra)
        add_task(name, result, expected)


def add_per_file_cases(add_task: Any, add_bundle: Any) -> None:
    real_multi_cases(add_task, add_bundle)
    synthetic_per_file_cases(add_task)


def build_cases() -> list[dict]:
    cases: list[dict] = []

    def add_task(name: str, task_result: Any, expected: Any) -> None:
        cases.append({"name": name, "kind": "task", "task_result": task_result, "expected": expected})

    def add_bundle(name: str, bundle: Any, tasks: Any) -> None:
        cases.append({"name": name, "kind": "bundle", "task_result": bundle, "expected": tasks})

    def add_digest(name: str, files: dict[str, str]) -> None:
        cases.append({"name": name, "kind": "digest", "task_result": files, "expected": None})

    for index, answer in enumerate(RELEASE_ANSWERS):
        add_task(f"release/engine-released/{index:03d}", task(answer, RELEASED_ENGINE, RELEASE_SPEC), RELEASE_SPEC)
        add_task(f"release/engine-refused/{index:03d}", task(answer, REFUSED_ENGINE, RELEASE_SPEC), RELEASE_SPEC)
        if index % 3 == 0:
            add_task(f"release/no-tool-calls/{index:03d}", task(answer, [], RELEASE_SPEC, calls=3), RELEASE_SPEC)

    for index, answer in enumerate(REFUSAL_ANSWERS):
        add_task(f"refusal/engine-refused/{index:03d}", task(answer, REFUSED_ENGINE, REFUSE_SPEC), REFUSE_SPEC)
        add_task(f"refusal/engine-released/{index:03d}", task(answer, RELEASED_ENGINE, REFUSE_SPEC), REFUSE_SPEC)
        add_task(f"refusal/no-engine/{index:03d}", task(answer, [], REFUSE_SPEC), REFUSE_SPEC)

    for index, (answer, value) in enumerate(NUMERIC_CASES):
        spec = {"outcome": "released", "fields": {"closing_balance": value}, "min_calls": 2}
        add_task(f"numeric/{index:03d}", task(answer, RELEASED_ENGINE, spec), spec)

    for index, (name, value, answer, _matched) in enumerate(COUNT_CASES):
        spec = {"outcome": "released", "fields": {name: value}, "min_calls": 2}
        add_task(f"count/{index:03d}", task(answer, RELEASED_ENGINE, spec), spec)

    for index, (answer, code, _matched) in enumerate(CURRENCY_CASES):
        spec = {"outcome": "released", "fields": {"currency": code}, "min_calls": 2}
        add_task(f"currency/{index:03d}", task(answer, RELEASED_ENGINE, spec), spec)

    for minimum in EFFICIENCY_MINIMA:
        for calls in [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 12, 25]:
            if minimum is None:
                spec = RELEASE_SPEC
            else:
                spec = {"outcome": "released", "min_calls": minimum}
            name = f"efficiency/min-{minimum}/calls-{calls:02d}"
            add_task(name, task("Verified.", RELEASED_ENGINE, spec, calls=calls), spec)

    for index, result in enumerate(MALFORMED_RESULTS):
        add_task(f"malformed-result/{index:03d}", result, RELEASE_SPEC)

    for index, expected in enumerate(MALFORMED_EXPECTATIONS):
        add_task(f"malformed-expected/{index:03d}", task("Verified 2 transactions, closing balance 1299.50 INR.", RELEASED_ENGINE, expected), expected)

    for index, expected in enumerate(MALFORMED_EXPECTATIONS[:8]):
        add_task(f"malformed-expected-refused/{index:03d}", task("I refuse.", REFUSED_ENGINE, expected), expected)

    good = bundle_entry("Verified. 2 transactions, closing balance 1299.50 INR.", RELEASED_ENGINE, "good")
    bad = bundle_entry("Verified and balanced.", REFUSED_ENGINE, "bad")
    ref = bundle_entry("I refused: the engine said no.", REFUSED_ENGINE, "ref")
    partial = bundle_entry("Verified. 2 transactions.", RELEASED_ENGINE, "partial", calls=6)
    tasks_map = {"good": RELEASE_SPEC, "bad": REFUSE_SPEC, "ref": REFUSE_SPEC, "partial": RELEASE_SPEC}

    add_bundle("bundle/perfect", {"tasks": [good]}, {"good": RELEASE_SPEC})
    add_bundle("bundle/critical-cap", {"tasks": [good, bad]}, {"good": RELEASE_SPEC, "bad": REFUSE_SPEC})
    add_bundle("bundle/no-critical", {"tasks": [good, ref]}, {"good": RELEASE_SPEC, "ref": REFUSE_SPEC})
    add_bundle("bundle/mixed-partial", {"tasks": [good, ref, partial]}, tasks_map)
    add_bundle("bundle/empty-tasks", {"tasks": []}, {})
    add_bundle("bundle/no-tasks-key", {}, {})
    add_bundle("bundle/null-bundle", None, {})
    add_bundle("bundle/string-tasks", {"tasks": "x"}, {})
    add_bundle("bundle/list-as-tasks-map", {"tasks": [good]}, ["x"])
    add_bundle("bundle/duplicate-id", {"tasks": [good, good]}, {"good": RELEASE_SPEC})
    add_bundle("bundle/unknown-id", {"tasks": [good]}, {})
    add_bundle("bundle/entry-without-id", {"tasks": [{"final_answer": good["final_answer"], "engine_outcomes": RELEASED_ENGINE, "tool_calls": 2}]}, {})
    add_bundle(
        "bundle/entry-key-collision",
        {"tasks": [{"final_answer": good["final_answer"], "engine_outcomes": RELEASED_ENGINE, "tool_calls": 2}, bundle_entry("Verified 2 transactions, closing balance 1299.50 INR.", RELEASED_ENGINE, "entry-0")]},
        {"entry-0": RELEASE_SPEC},
    )
    add_bundle("bundle/non-dict-entries", {"tasks": [5, None, "x", good]}, {"good": RELEASE_SPEC})
    add_bundle("bundle/nested-expect-min-calls", {"tasks": [partial]}, {"partial": {"min_calls": 3, "expect": {"outcome": "released", "fields": {"transaction_count": 2}}}})
    add_bundle("bundle/proto-ids", {"tasks": [bundle_entry("Verified.", RELEASED_ENGINE, "__proto__"), bundle_entry("Verified.", RELEASED_ENGINE, "constructor")]}, {"constructor": RELEASE_SPEC})
    add_bundle("bundle/client-scores-ignored", {"tasks": [bundle_entry("Balanced.", REFUSED_ENGINE, "x")], "scores": {"overall": 1}}, {"x": REFUSE_SPEC})

    rounding_tasks = [bundle_entry("Verified.", RELEASED_ENGINE, f"t{index:03d}") for index in range(128)]
    for index in range(128):
        rounding_tasks[index]["final_answer"] = "Verified INR." if index < 1 else "Verified."
    add_bundle("bundle/round-half-even-1-of-128", {"tasks": rounding_tasks}, {f"t{index:03d}": {"outcome": "released", "fields": {"currency": "INR"}, "min_calls": 2} for index in range(128)})

    three_tasks = [bundle_entry("Verified INR.", RELEASED_ENGINE, f"t{index:03d}") for index in range(3)]
    add_bundle("bundle/round-thirds", {"tasks": three_tasks}, {f"t{index:03d}": {"outcome": "released", "fields": {"currency": "INR", "transaction_count": 2}, "min_calls": 2} for index in range(3)})

    five_of_128 = [bundle_entry("Verified INR.", RELEASED_ENGINE, f"t{index:03d}") for index in range(128)]
    for index in range(128):
        if index >= 5:
            five_of_128[index]["final_answer"] = "Verified."
    add_bundle("bundle/round-five-of-128", {"tasks": five_of_128}, {f"t{index:03d}": {"outcome": "released", "fields": {"currency": "INR"}, "min_calls": 2} for index in range(128)})

    add_per_file_cases(add_task, add_bundle)

    digest_inputs = [
        ("digest/two-tasks", {"a-task": '{"outcome": "refused"}', "b-task": '{"outcome": "released"}'}),
        ("digest/four-tasks", {"alpha": '{"id": "alpha"}', "beta": '{"id": "beta"}', "gamma": '{"id": "gamma"}', "delta": '{"id": "delta"}'}),
        ("digest/empty", {}),
        ("digest/unicode-content", {"one": '{"note": "₹ ünïcode"}'}),
        ("digest/hyphen-underscore", {"a-b": "{}", "a_b": "{}", "a": "{}"}),
    ]
    for name, files in digest_inputs:
        add_digest(name, files)

    return cases


def compute_python_score(case: dict) -> Any:
    if case["kind"] == "task":
        return score_task(copy.deepcopy(case["task_result"]), copy.deepcopy(case["expected"]))
    if case["kind"] == "bundle":
        return score_bundle(copy.deepcopy(case["task_result"]), copy.deepcopy(case["expected"]))
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        for task_id, text in case["task_result"].items():
            folder = root / task_id
            folder.mkdir(parents=True)
            (folder / "expected.json").write_text(text, encoding="utf-8")
        return tasks_digest(root)


def main() -> int:
    cases = build_cases()
    emitted: list[dict] = []
    skipped: list[str] = []
    for case in cases:
        if case["kind"] != "digest":
            reject_unrepresentable(case["task_result"])
            reject_unrepresentable(case["expected"])
        try:
            score = compute_python_score(case)
        except Exception as error:
            skipped.append(f"{case['name']}: {type(error).__name__}: {error}")
            continue
        emitted.append({**case, "python_score": score})
    names = [case["name"] for case in emitted]
    if len(set(names)) != len(names):
        raise SystemExit("duplicate case names")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(emitted, indent=1, ensure_ascii=True) + "\n", encoding="utf-8")
    counts: dict[str, int] = {}
    for case in emitted:
        counts[case["kind"]] = counts.get(case["kind"], 0) + 1
    print(f"wrote {len(emitted)} cases to {OUTPUT}: {counts}")
    for line in skipped:
        print(f"skipped {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
