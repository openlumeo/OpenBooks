"""Golden cases for the release-two inputs: tax statements, FIRA, trial balance, .xlsx and PDF/scan statements.

Every 'ok' case has refused twins: a printed total or balance moved by one unit, plus structural breakage.
Scans are rendered from the same rows, so a refusal there means OCR or the gate caught the error.
"""
from __future__ import annotations

import io
import random
from decimal import ROUND_HALF_UP, Decimal

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
TB_ROWS = [("Cash", "5000.00", ""), ("Receivables", "3000.50", ""), ("Payables", "", "2000.25"),
           ("Capital", "", "5000.00"), ("Revenue", "", "1000.25")]


def _fira_rows() -> tuple[list[str], str]:
    rows, tot_inr, tot_net = [], Decimal(0), Decimal(0)
    for k, (fx, rate) in enumerate([("1000.00", "83.2150"), ("2500.50", "82.9000"), ("150.25", "83.1000")], 1):
        inr = (Decimal(fx) * Decimal(rate)).quantize(Decimal("0.01"), ROUND_HALF_UP)
        charges = Decimal("15.00")
        rows.append(f"FIRA{k:03d},{k:02d}/05/2025,Remitter {k},USD,{fx},{rate},{inr},{charges},{inr - charges}")
        tot_inr += inr
        tot_net += inr - charges
    return rows, f"Total,,,,,,{tot_inr},,{tot_net}"


def _csv(head: str, rows: list[str], total: str | None = None) -> str:
    return "\n".join([head] + rows + ([total] if total else [])) + "\n"


def _xlsx(rows: list[list]) -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Workpaper"
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _num(s: str):
    return float(s) if s else None


def _pdf_rows(rng: random.Random, n: int) -> list[list[str]]:
    from datetime import date, timedelta

    from .golden import bank_rows
    from .synth import merchant_rows

    rows = merchant_rows(bank_rows(rng, n), rng)
    for k, r in enumerate(rows):
        r[0] = (date(2026, 1, 1) + timedelta(days=k // 2)).strftime("%d/%m/%Y")
    return rows


def _clean_layout(rng: random.Random):
    from .synth import random_layout

    lay = random_layout(rng)
    lay.font, lay.size, lay.right_amounts, lay.has_header, lay.drcr_balance = "helv", 9, True, True, False
    lay.grouping, lay.date_fmt, lay.line_h = "western", "%d/%m/%Y", 15
    return lay


def _bump(s: str) -> str:
    return f"{Decimal(s) + Decimal('0.01'):.2f}"


def build_pdfs(root, rng: random.Random, scans: bool) -> None:
    import fitz

    from .golden import OPEN, _write
    from .synth import random_layout, render, to_scan

    ok, refused, mism = "ok", "refused", "BALANCE_MISMATCH"
    P = {"currency": "INR"}
    rows = _pdf_rows(rng, 10)
    close = rows[-1][4]

    def pdf(rs, lay=None, opening=str(OPEN), closing=close):
        return render(rs, opening, lay or _clean_layout(random.Random(3)), random.Random(5), closing=closing)[0]

    _write(root, "ok_pdf_text", "in.pdf", pdf(rows), ok, params=P)
    for k in range(4):
        lay = random_layout(random.Random(100 + k))
        lay.has_header = True
        _write(root, f"ok_pdf_layout_{k}", "in.pdf", pdf(rows, lay), ok, params=P)
    _write(root, "ok_pdf_multipage", "in.pdf", pdf(_pdf_rows(random.Random(9), 70), closing=None), ok, params=P)
    _write(root, "ok_pdf_no_printed_closing", "in.pdf", pdf(rows, closing=None), ok, params=P)
    _write(root, "ok_pdf_opening_supplied", "in.pdf", pdf(rows, opening=None, closing=None), ok, params={"currency": "INR", "opening": str(OPEN)})
    bal = [r[:] for r in rows]
    bal[4][4] = _bump(bal[4][4])
    _write(root, "bad_pdf_balance_cent", "in.pdf", pdf(bal), refused, mism, P)
    amt = [r[:] for r in rows]
    col = 2 if amt[3][2] else 3
    amt[3][col] = _bump(amt[3][col])
    _write(root, "bad_pdf_amount_cent", "in.pdf", pdf(amt), refused, mism, P)
    _write(root, "bad_pdf_printed_closing_cent", "in.pdf", pdf(rows, closing=_bump(close)), refused, mism, P)
    _write(root, "bad_pdf_opening_conflict", "in.pdf", pdf(rows), refused, "PARSE_ERROR", {"currency": "INR", "opening": "1000.01"})
    _write(root, "bad_pdf_no_opening", "in.pdf", pdf(rows, opening=None, closing=None), refused, "PARSE_ERROR", P)
    badd = [r[:] for r in rows]
    badd[2][0] = "31/02/2026"
    _write(root, "bad_pdf_impossible_date", "in.pdf", pdf(badd), refused, "PARSE_ERROR", P)
    note = fitz.open()
    note.new_page().insert_text((50, 80), "Dear customer, this letter confirms that your account remains active and in good standing.", fontsize=10)
    _write(root, "bad_pdf_not_a_statement", "in.pdf", note.tobytes(), refused, "UNKNOWN_LAYOUT")
    _write(root, "bad_pdf_garbage", "in.pdf", b"%PDF-1.4 not really", refused, ["UNSUPPORTED_INPUT", "UNKNOWN_LAYOUT"])
    from .synth import with_failed_rows

    def find(pred):
        for s in range(400):
            lay = random_layout(random.Random(s), rich=True)
            if lay.font == "helv" and pred(lay):
                lay.has_header = True
                return lay
        raise RuntimeError("no layout found")

    single = find(lambda l: l.single and not l.ccy_prefix)
    _write(root, "ok_pdf_single_amount_crdr", "in.pdf", pdf(rows, single), ok, params=P)
    swap = [r[:] for r in rows]
    swap[3][2], swap[3][3] = swap[3][3], swap[3][2]
    _write(root, "bad_pdf_single_wrong_marker", "in.pdf", pdf(swap, single), refused, mism, P)
    _write(root, "ok_pdf_rs_prefix_watermark", "in.pdf", pdf(rows, find(lambda l: l.ccy_prefix and l.watermark)), ok, params=P)
    _write(root, "ok_pdf_wrapped_description_above", "in.pdf", pdf(rows, find(lambda l: l.wrap_above)), ok, params=P)
    failed = with_failed_rows(rows, random.Random(4), 2)
    lay_f = _clean_layout(random.Random(3))
    _write(root, "ok_pdf_failed_rows", "in.pdf", pdf(failed, lay_f, closing=failed[-1][4]), ok, params=P)
    moved = [r[:] for r in failed]
    i = next(k for k, r in enumerate(moved) if not (r[2] or r[3]))
    moved[i][4] = _bump(moved[i][4])
    _write(root, "bad_pdf_failed_row_moves_balance", "in.pdf", pdf(moved, lay_f, closing=failed[-1][4]), refused, mism, P)
    if not scans:
        return
    srows, any_code = _pdf_rows(random.Random(21), 14), ["BALANCE_MISMATCH", "PARSE_ERROR", "LOW_CONFIDENCE"]
    base = pdf(srows, closing=srows[-1][4])
    _write(root, "ok_scan_pdf", "in.pdf", to_scan(base, random.Random(1)), ok, params=P)
    _write(root, "ok_scan_multipage", "in.pdf", to_scan(pdf(_pdf_rows(random.Random(22), 60), closing=None), random.Random(2)), ok, params=P)
    img = fitz.open(stream=to_scan(base, random.Random(3)), filetype="pdf")[0].get_pixmap(dpi=200).tobytes("png")
    _write(root, "ok_scan_png", "in.png", img, ok, params=P)
    sb = [r[:] for r in srows]
    sb[6][4] = _bump(sb[6][4])
    _write(root, "bad_scan_balance_cent", "in.pdf", to_scan(pdf(sb, closing=srows[-1][4]), random.Random(4)), refused, any_code, P)
    sa = [r[:] for r in srows]
    sa[5][3 if sa[5][3] else 2] = _bump(sa[5][3] or sa[5][2])
    _write(root, "bad_scan_amount_cent", "in.pdf", to_scan(pdf(sa, closing=srows[-1][4]), random.Random(5)), refused, any_code, P)


def build_docs(root, rng: random.Random, scans: bool = False) -> None:
    from .golden import BANK_PARAMS, _write, bank_rows

    build_pdfs(root, rng, scans)

    ok, refused = "ok", "refused"
    mismatch = "BALANCE_MISMATCH"
    _write(root, "ok_tds", "in.csv", _csv(TDS_HEAD, TDS_ROWS, TDS_TOTAL), ok)
    _write(root, "bad_tds_total_cent", "in.csv", _csv(TDS_HEAD, TDS_ROWS, TDS_TOTAL.replace("7500.05,7500.05", "7500.06,7500.05")), refused, mismatch)
    _write(root, "bad_tds_row_cent", "in.csv", _csv(TDS_HEAD, [TDS_ROWS[0].replace("2000.00,2000.00", "2000.01,2000.00")] + TDS_ROWS[1:], TDS_TOTAL), refused, mismatch)
    _write(root, "bad_tds_no_total", "in.csv", _csv(TDS_HEAD, TDS_ROWS), refused, mismatch)
    _write(root, "bad_tds_bad_date", "in.csv", _csv(TDS_HEAD, [TDS_ROWS[0].replace("15/04/2025", "31/02/2025")] + TDS_ROWS[1:], TDS_TOTAL), refused, "PARSE_ERROR")
    _write(root, "ok_ais", "in.csv", _csv(AIS_HEAD, AIS_ROWS, AIS_TOTAL), ok)
    _write(root, "bad_ais_total_cent", "in.csv", _csv(AIS_HEAD, AIS_ROWS, AIS_TOTAL.replace("1216345.67", "1216345.68")), refused, mismatch)
    fr, ft = _fira_rows()
    _write(root, "ok_fira", "in.csv", _csv(FIRA_HEAD, fr, ft), ok)
    _write(root, "bad_fira_fx_mismatch", "in.csv", _csv(FIRA_HEAD, [fr[0].replace("83215.00,15.00,83200.00", "83220.00,15.00,83205.00")] + fr[1:], ft), refused, mismatch)
    _write(root, "bad_fira_cent_vs_total", "in.csv", _csv(FIRA_HEAD, [fr[0].replace("83215.00,15.00,83200.00", "83215.01,15.00,83200.01")] + fr[1:], ft), refused, mismatch)
    _write(root, "bad_fira_net_charges", "in.csv", _csv(FIRA_HEAD, [fr[0].replace("83200.00", "83200.01")] + fr[1:], ft), refused, mismatch)
    tb = [",".join(r) for r in TB_ROWS]
    _write(root, "ok_tb_csv", "in.csv", _csv(TB_HEAD, tb), ok, params={"currency": "INR"})
    bad_tb = tb[:-1] + ["Revenue,,1000.26"]
    _write(root, "bad_tb_cent", "in.csv", _csv(TB_HEAD, bad_tb), refused, mismatch, {"currency": "INR"})
    grid = [["Trial balance FY25"], [], ["Account", "Debit", "Credit"]] + [[a, _num(d), _num(c)] for a, d, c in TB_ROWS]
    _write(root, "ok_tb_xlsx", "in.xlsx", _xlsx(grid + [["Total", 8000.50, 8000.50]]), ok, params={"currency": "INR"})
    bad_grid = grid[:-1] + [["Revenue", None, 1000.26]]
    _write(root, "bad_tb_xlsx_cent", "in.xlsx", _xlsx(bad_grid), refused, mismatch, {"currency": "INR"})
    _write(root, "bad_tb_xlsx_formula", "in.xlsx", _xlsx(grid + [["Total", "=SUM(B4:B8)", "=SUM(C4:C8)"]]), refused, "PARSE_ERROR", {"currency": "INR"})
    _write(root, "bad_xlsx_garbage", "in.xlsx", b"not a workbook", refused, "UNSUPPORTED_INPUT")
    rows = bank_rows(rng, 6)
    bank_grid = [["Date", "Narration", "Debit", "Credit", "Balance"]] + [[r[0], r[1], _num(r[2]), _num(r[3]), _num(r[4])] for r in rows]
    _write(root, "ok_bank_xlsx", "in.xlsx", _xlsx(bank_grid), ok, params=BANK_PARAMS)
    bank_bad = [r[:] for r in bank_grid]
    bank_bad[3][4] = round(bank_bad[3][4] + 0.01, 2)
    _write(root, "bad_bank_xlsx_cent", "in.xlsx", _xlsx(bank_bad), refused, mismatch, BANK_PARAMS)
