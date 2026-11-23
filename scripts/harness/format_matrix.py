from __future__ import annotations

import argparse
import asyncio
import base64
import csv
import datetime
import io
import json
import os
import random
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[min(2, len(Path(__file__).resolve().parents) - 1)]
IMAGE = "openbooks-mcp-sbx"
SERVER = ["node", "/work/js/mcp/dist/cli.js"]
OPENING = Decimal("1000.00")
TRANSACTIONS = [
    ("2026-01-02", "Salary January", Decimal("45000.00")),
    ("2026-01-03", "Rent payment", Decimal("-12500.00")),
    ("2026-01-05", "Grocery store", Decimal("-1843.75")),
    ("2026-01-08", "Electricity bill", Decimal("-2310.40")),
    ("2026-01-12", "Client invoice 1042", Decimal("18250.00")),
    ("2026-01-15", "ATM withdrawal", Decimal("-5000.00")),
    ("2026-01-20", "Insurance premium", Decimal("-3999.99")),
    ("2026-01-28", "Interest credit", Decimal("112.35")),
]
TAMPER_INDEX = 1
TAMPER_DELTA = Decimal("450.00")
CLOSING = OPENING + sum(t[2] for t in TRANSACTIONS)
CLOSING_ALTERED = CLOSING + Decimal("1000.00")
CODES = {"UNKNOWN_LAYOUT", "UNSUPPORTED_INPUT", "PARSE_ERROR", "BALANCE_MISMATCH", "LOW_CONFIDENCE", "OUTPUT_INVALID"}
SCAN_WIDTH, SCAN_HEIGHT = 1654, 2339
COLUMNS = (70, 330, 960, 1180, 1390)
HEADERS = ("Date", "Description", "Debit", "Credit", "Balance")
FONT_DIR = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"

CSV_PARAMS = {"currency": "INR", "date_order": "dmy", "opening": "1000.00"}
PRINTED_PARAMS = {"currency": "INR", "date_order": "dmy"}
BARE_PARAMS: dict = {}


def dmy(iso: str) -> str:
    year, month, day = iso.split("-")
    return f"{day}/{month}/{year}"


def money(value: Decimal) -> str:
    return f"{value:.2f}"


def running(rows=TRANSACTIONS, opening: Decimal = OPENING) -> list[Decimal]:
    balance, out = opening, []
    for _, _, amount in rows:
        balance += amount
        out.append(balance)
    return out


def tampered(rows=TRANSACTIONS) -> list[tuple]:
    out = list(rows)
    date, name, amount = out[TAMPER_INDEX]
    out[TAMPER_INDEX] = (date, name, amount - TAMPER_DELTA if amount < 0 else amount + TAMPER_DELTA)
    return out


def split(amount: Decimal) -> tuple[str, str]:
    return (money(-amount), "") if amount < 0 else ("", money(amount))


def csv_text(head: list[str], body: list[list[str]], quote_all: bool = False) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n", quoting=csv.QUOTE_ALL if quote_all else csv.QUOTE_MINIMAL)
    writer.writerow(head)
    writer.writerows(body)
    return buffer.getvalue()


def csv_debit_credit(head: list[str], rows: list[tuple], balances: list[Decimal], thousands: bool = False) -> str:
    fmt = (lambda v: f"{Decimal(v):,.2f}" if v else "") if thousands else (lambda v: v)
    body = []
    for (date, name, amount), balance in zip(rows, balances):
        debit, credit = split(amount)
        shown = f"{balance:,.2f}" if thousands else money(balance)
        body.append([dmy(date), name, fmt(debit), fmt(credit), shown])
    return csv_text(head, body)


def csv_signed(rows: list[tuple], balances: list[Decimal]) -> str:
    body = [[dmy(d), n, money(a), money(b)] for (d, n, a), b in zip(rows, balances)]
    return csv_text(["Date", "Description", "Amount", "Balance"], body)


def mt940(rows: list[tuple], closing: Decimal = CLOSING) -> str:
    lines = [":20:STMT001", ":25:12345678/9876543", ":28C:1/1", f":60F:C260101INR{money(OPENING).replace('.', ',')}"]
    for date, name, amount in rows:
        short = date[2:4] + date[5:7] + date[8:10]
        mark = "C" if amount > 0 else "D"
        lines.append(f":61:{short}{short[2:]}{mark}{money(abs(amount)).replace('.', ',')}NTRFNONREF//BANKREF")
        lines.append(f":86:{name}")
    mark = "C" if closing >= 0 else "D"
    lines.append(f":62F:{mark}260128INR{money(abs(closing)).replace('.', ',')}")
    return "\n".join(lines) + "\n"


def ofx(rows: list[tuple], closing: Decimal = CLOSING, qfx: bool = False) -> str:
    head = "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
    signon = "<SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20260131120000<LANGUAGE>ENG"
    signon += "<FI><ORG>Example Bank<FID>1234</FI><INTU.BID>1234</SONRS></SIGNONMSGSRSV1>\n" if qfx else "</SONRS></SIGNONMSGSRSV1>\n"
    out = [head + "<OFX>\n" + signon + "<BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS><STMTRS>\n<CURDEF>INR"]
    out.append("<BANKACCTFROM><BANKID>123456<ACCTID>123456789<ACCTTYPE>CHECKING</BANKACCTFROM>\n<BANKTRANLIST>\n<DTSTART>20260101<DTEND>20260131")
    for index, (date, name, amount) in enumerate(rows, 1):
        kind = "CREDIT" if amount > 0 else "DEBIT"
        stamp = date.replace("-", "") + "120000"
        out.append(f"<STMTTRN><TRNTYPE>{kind}<DTPOSTED>{stamp}<TRNAMT>{money(amount)}<FITID>T{index:04d}<NAME>{name}</STMTTRN>")
    out.append(f"</BANKTRANLIST>\n<LEDGERBAL><BALAMT>{money(closing)}<DTASOF>20260131</LEDGERBAL>\n</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n")
    return "\n".join(out)


def camt(rows: list[tuple], closing: Decimal = CLOSING) -> str:
    def balance(code: str, value: Decimal, day: str) -> str:
        mark = "CRDT" if value >= 0 else "DBIT"
        return (f'<Bal><Tp><CdOrPrtry><Cd>{code}</Cd></CdOrPrtry></Tp><Amt Ccy="INR">{money(abs(value))}</Amt>'
                f"<CdtDbtInd>{mark}</CdtDbtInd><Dt><Dt>{day}</Dt></Dt></Bal>")

    entries = ""
    for index, (date, name, amount) in enumerate(rows, 1):
        mark = "CRDT" if amount > 0 else "DBIT"
        entries += (f'<Ntry><Amt Ccy="INR">{money(abs(amount))}</Amt><CdtDbtInd>{mark}</CdtDbtInd><Sts>BOOK</Sts>'
                    f"<BookgDt><Dt>{date}</Dt></BookgDt><AcctSvcrRef>REF{index}</AcctSvcrRef>"
                    f"<NtryDtls><TxDtls><RmtInf><Ustrd>{name}</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>")
    body = (f"<Stmt><Id>S1</Id><Acct><Id><IBAN>DE89370400440532013000</IBAN></Id><Ccy>INR</Ccy></Acct>"
            f"{balance('OPBD', OPENING, '2026-01-01')}{balance('CLBD', closing, '2026-01-28')}{entries}</Stmt>")
    ns = ' xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"'
    return f'<?xml version="1.0" encoding="UTF-8"?><Document{ns}><BkToCstmrStmt>{body}</BkToCstmrStmt></Document>'


def xlsx_bytes(rows: list[tuple], balances: list[Decimal], real_dates: bool) -> bytes:
    import openpyxl

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Statement"
    sheet.append(list(HEADERS) if real_dates else ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"])
    for (date, name, amount), balance in zip(rows, balances):
        when = datetime.datetime.strptime(date, "%Y-%m-%d") if real_dates else dmy(date)
        sheet.append([when, name, float(-amount) if amount < 0 else None, float(amount) if amount > 0 else None, float(balance)])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def statement_lines(rows: list[tuple], closing: Decimal, balances: list[Decimal] | None = None) -> list[list[str]]:
    shown = balances if balances is not None else running()
    lines = [["Statement of Account (INR)"], [f"Opening Balance: {money(OPENING)}"], list(HEADERS)]
    for (date, name, amount), balance in zip(rows, shown):
        debit, credit = split(amount)
        lines.append([dmy(date), name, debit, credit, money(balance)])
    lines.append([f"Closing Balance: {money(closing)}"])
    return lines


def text_pdf(rows: list[tuple], closing: Decimal) -> bytes:
    sys.path.insert(0, str(ROOT / "packages" / "py" / "openbooks" / "tests" / "statements"))
    from pdfmaker import statement_pdf

    body = [(dmy(d), n, *split(a), money(b)) for (d, n, a), b in zip(rows, running())]
    return statement_pdf(body, opening=money(OPENING), closing=money(closing))


def load_font(names: list[str], size: int):
    from PIL import ImageFont

    for name in names:
        path = FONT_DIR / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise SystemExit(f"none of the fonts {names} found in {FONT_DIR}")


def grain(image, sigma: float, seed: int):
    from PIL import Image, ImageChops

    random.seed(seed)
    noise = Image.effect_noise(image.size, sigma).convert("RGB")
    return ImageChops.add(image, noise, 1.0, -128)


def print_scan(lines: list[list[str]], angle: float, sigma: float, seed: int):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (SCAN_WIDTH, SCAN_HEIGHT), (250, 250, 247))
    draw = ImageDraw.Draw(image)
    font = load_font(["arial.ttf", "Arial.ttf"], 34)
    y = 160
    for line in lines:
        positions = COLUMNS if len(line) == 5 else (COLUMNS[0],)
        for x, cell in zip(positions, line):
            draw.text((x, y), cell, fill=(20, 20, 20), font=font)
        y += 74 if len(line) == 5 else 110
    image = image.rotate(angle, fillcolor=(250, 250, 247), resample=Image.BICUBIC)
    return grain(image, sigma, seed)


def handwritten_scan(lines: list[list[str]], font_names: list[str], seed: int):
    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    page = Image.new("RGB", (SCAN_WIDTH, SCAN_HEIGHT), (244, 240, 228))
    ruled = ImageDraw.Draw(page)
    for y in range(220, SCAN_HEIGHT, 74):
        ruled.line([(40, y), (SCAN_WIDTH - 40, y)], fill=(200, 205, 215), width=2)
    font = load_font(font_names, 44)
    y = 150
    for line in lines:
        positions = COLUMNS if len(line) == 5 else (COLUMNS[0],)
        for x, cell in zip(positions, line):
            layer = Image.new("RGBA", (700, 120), (0, 0, 0, 0))
            ImageDraw.Draw(layer).text((20, 30), cell, fill=(25, 35, 110, 255), font=font)
            layer = layer.rotate(rng.uniform(-3.0, 3.0), resample=Image.BICUBIC)
            page.paste(layer, (x - 20 + rng.randint(-6, 6), y + rng.randint(-8, 8)), layer)
        y += 74 if len(line) == 5 else 110
    page = page.rotate(rng.uniform(1.0, 1.8), fillcolor=(244, 240, 228), resample=Image.BICUBIC)
    return grain(page, 14.0, seed)


def shrink(image):
    from PIL import Image

    return image.resize((SCAN_WIDTH * 3 // 4, SCAN_HEIGHT * 3 // 4), Image.LANCZOS)


def save_png(image, path: Path) -> None:
    shrink(image).convert("L").save(path, "PNG", optimize=True)


def save_jpeg(image, path: Path) -> None:
    shrink(image).save(path, "JPEG", quality=70)


def save_image_pdf(image, path: Path) -> None:
    shrink(image).convert("RGB").save(path, "PDF", resolution=150.0)


def manifest_entry(name: str, fmt: str, variant: str, expect: str, params: dict, tampered_file: bool = False, altered: bool = False) -> dict:
    return {"name": name, "format": fmt, "variant": variant, "expect": expect, "params": params, "tampered": tampered_file, "altered": altered}


def generate(out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    balances = running()
    bad = tampered()

    def put(name: str, payload: bytes | str, fmt: str, variant: str, expect: str, params: dict, **flags) -> None:
        data = payload.encode("utf-8") if isinstance(payload, str) else payload
        (out / name).write_bytes(data)
        entries.append(manifest_entry(name, fmt, variant, expect, params, **flags))

    layouts = [
        ("csv_hdfc_style", ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"], False),
        ("csv_generic_debit_credit", ["Date", "Description", "Debit", "Credit", "Balance"], False),
        ("csv_indian_commas", ["Txn Date", "Particulars", "Debit", "Credit", "Balance"], True),
    ]
    for stem, head, thousands in layouts:
        put(f"{stem}.csv", csv_debit_credit(head, TRANSACTIONS, balances, thousands), "csv", stem, "release", CSV_PARAMS)
        put(f"{stem}_tampered.csv", csv_debit_credit(head, bad, balances, thousands), "csv", f"{stem} tampered", "refuse", CSV_PARAMS, tampered_file=True)
    put("csv_signed_amount.csv", csv_signed(TRANSACTIONS, balances), "csv", "signed amount", "release", CSV_PARAMS)
    put("csv_signed_amount_tampered.csv", csv_signed(bad, balances), "csv", "signed amount tampered", "refuse", CSV_PARAMS, tampered_file=True)

    for extension in ("sta", "mt940"):
        put(f"statement.{extension}", mt940(TRANSACTIONS), extension, "clean", "release", BARE_PARAMS)
        put(f"statement_tampered.{extension}", mt940(bad), extension, "tampered", "refuse", BARE_PARAMS, tampered_file=True)
    for extension in ("ofx", "qfx"):
        put(f"statement.{extension}", ofx(TRANSACTIONS, qfx=extension == "qfx"), extension, "clean", "release", CSV_PARAMS)
        put(f"statement_tampered.{extension}", ofx(bad, qfx=extension == "qfx"), extension, "tampered", "refuse", CSV_PARAMS, tampered_file=True)
    put("statement_camt053.xml", camt(TRANSACTIONS), "camt053", "clean", "release", BARE_PARAMS)
    put("statement_camt053_tampered.xml", camt(bad), "camt053", "tampered", "refuse", BARE_PARAMS, tampered_file=True)

    put("statement_text_dates.xlsx", xlsx_bytes(TRANSACTIONS, balances, False), "xlsx", "text dates", "release", CSV_PARAMS)
    put("statement_real_dates.xlsx", xlsx_bytes(TRANSACTIONS, balances, True), "xlsx", "datetime cells", "release", CSV_PARAMS)
    put("statement_text_dates_tampered.xlsx", xlsx_bytes(bad, balances, False), "xlsx", "text dates tampered", "refuse", CSV_PARAMS, tampered_file=True)

    put("statement_text.pdf", text_pdf(TRANSACTIONS, CLOSING), "pdf-text", "clean", "release", PRINTED_PARAMS)
    put("statement_text_tampered.pdf", text_pdf(bad, CLOSING), "pdf-text", "tampered", "refuse", PRINTED_PARAMS, tampered_file=True)

    printed = statement_lines(TRANSACTIONS, CLOSING)
    scan = print_scan(printed, 0.3, 1.5, 1)
    scan_skewed = print_scan(printed, 1.2, 14.0, 2)
    scan_png, scan_pdf, scan_skew_png = out / "scan_printed.png", out / "scan_printed.pdf", out / "scan_printed_skewed.jpg"
    save_png(scan, scan_png)
    save_image_pdf(scan, scan_pdf)
    save_jpeg(scan_skewed, scan_skew_png)
    entries += [
        manifest_entry("scan_printed.png", "png-scan", "printed", "release", PRINTED_PARAMS),
        manifest_entry("scan_printed.pdf", "pdf-scan", "printed", "release", PRINTED_PARAMS),
        manifest_entry("scan_printed_skewed.jpg", "jpg-scan", "printed skewed 1.2deg noisy", "release", PRINTED_PARAMS),
    ]
    tampered_scan = print_scan(statement_lines(bad, CLOSING), 0.3, 1.5, 3)
    save_png(tampered_scan, out / "scan_printed_tampered.png")
    entries.append(manifest_entry("scan_printed_tampered.png", "png-scan", "printed tampered", "refuse", PRINTED_PARAMS, tampered_file=True))

    altered = statement_lines(TRANSACTIONS, CLOSING_ALTERED)
    for stem, fonts in (("ink_free", ["Inkfree.ttf"]), ("segoe_print", ["segoepr.ttf"])):
        save_jpeg(handwritten_scan(printed, fonts, 11), out / f"handwritten_{stem}.jpg")
        entries.append(manifest_entry(f"handwritten_{stem}.jpg", "jpg-handwritten", f"{stem} clean", "safe", PRINTED_PARAMS))
        save_jpeg(handwritten_scan(altered, fonts, 12), out / f"handwritten_{stem}_altered_totals.jpg")
        entries.append(manifest_entry(f"handwritten_{stem}_altered_totals.jpg", "jpg-handwritten", f"{stem} altered totals", "refuse", PRINTED_PARAMS, altered=True))

    truth = {
        "opening": money(OPENING),
        "closing": money(CLOSING),
        "transactions": [{"date": d, "description": n, "amount": money(abs(a)), "direction": "credit" if a > 0 else "debit"} for d, n, a in TRANSACTIONS],
    }
    (out / "manifest.json").write_text(json.dumps({"truth": truth, "files": entries}, indent=1), encoding="utf-8")
    return entries


def signed(item: dict) -> str:
    amount = Decimal(item["amount"]["amount"])
    return money(amount if item["direction"] == "credit" else -amount)


def compare(truth: dict, batches: list[dict], transactions: list[dict]) -> dict:
    want = [(t["date"], t["amount"], t["direction"]) for t in truth["transactions"]]
    got = [(t["date"], t["amount"]["amount"], t["direction"]) for t in transactions]
    problems = []
    if got != want:
        problems.append(f"transactions differ ({len(got)} read, {len(want)} expected)")
    closings = [b["closing"]["amount"] for b in batches]
    openings = [b["opening"]["amount"] for b in batches]
    if closings != [truth["closing"]]:
        problems.append(f"closing {closings} != {truth['closing']}")
    if openings != [truth["opening"]]:
        problems.append(f"opening {openings} != {truth['opening']}")
    return {"exact": not problems, "problems": problems}


def step_summary(step: dict) -> dict:
    if "error" in step:
        return {"status": "error", "code": step["error"]["code"], "message": step["error"].get("message", "")}
    result = step["result"]
    error = result.get("error") or {}
    return {"status": result["status"], "code": error.get("code"), "message": error.get("message", "")[:160]}


async def drive(directory: Path) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    files = manifest["files"]
    truth = manifest["truth"]
    uploads = {f["name"]: {"filename": f["name"], "content_base64": base64.b64encode((directory / f["name"]).read_bytes()).decode()} for f in files}
    results: dict[str, dict] = {f["name"]: {} for f in files}

    async with stdio_client(StdioServerParameters(command=SERVER[0], args=SERVER[1:])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            async def execute(steps: list[dict], parallel: bool = False) -> list[dict]:
                reply = await session.call_tool("execute", {"steps": steps, "parallel": parallel, "stop_on_error": False})
                content = reply.structured_content
                if content is None or "steps" not in content:
                    raise RuntimeError(f"execute failed: {content}")
                return content["steps"]

            for f in files:
                print("file", f["name"], file=sys.stderr, flush=True)
                params = {**f["params"], **uploads[f["name"]]}
                steps = [{"id": "up", "operation": "process_upload", "arguments": params}]
                first = (await execute(steps))[0]
                entry = step_summary(first)
                if entry["status"] == "ok":
                    follow = [
                        {"id": "up", "operation": "process_upload", "arguments": params},
                        {"id": "b", "operation": "records", "arguments": {"from_step": "up", "collection": "batches"}},
                        {"id": "t", "operation": "records", "arguments": {"from_step": "up", "collection": "transactions", "limit": 10}},
                    ]
                    steps_out = await execute(follow)
                    batches = steps_out[1]["result"]["items"]
                    transactions = steps_out[2]["result"]["items"]
                    total = steps_out[2]["result"]["total"]
                    offset = 10
                    while len(transactions) < total:
                        more = await execute([
                            {"id": "up", "operation": "process_upload", "arguments": params},
                            {"id": "t", "operation": "records", "arguments": {"from_step": "up", "collection": "transactions", "limit": 10, "offset": offset}},
                        ])
                        transactions += more[1]["result"]["items"]
                        offset += 10
                    entry["figures"] = compare(truth, batches, transactions)
                    entry["read_transactions"] = len(transactions)
                results[f["name"]]["sequential"] = entry

            groups: dict[str, list[dict]] = {}
            for f in files:
                groups.setdefault(json.dumps(f["params"], sort_keys=True), []).append(f)
            for key, members in groups.items():
                common = json.loads(key)
                for start in range(0, len(members), 8):
                    chunk = members[start:start + 8]
                    steps = [{"id": "vm", "operation": "verify_many", "arguments": {**common, "uploads": [uploads[m["name"]] for m in chunk]}}]
                    out = (await execute(steps))[0]
                    for member, item in zip(chunk, out["result"]["files"] if "result" in out else []):
                        results[member["name"]]["verify_many"] = {"status": item.get("status"), "code": item.get("code")}
                    if "error" in out:
                        for member in chunk:
                            results[member["name"]]["verify_many"] = {"status": "error", "code": out["error"]["code"]}

            for start in range(0, len(files), 8):
                chunk = files[start:start + 8]
                steps = [{"id": f"p{i}", "operation": "process_upload", "arguments": {**m["params"], **uploads[m["name"]]}} for i, m in enumerate(chunk)]
                for member, item in zip(chunk, await execute(steps, parallel=True)):
                    results[member["name"]]["parallel"] = step_summary(item)
    return {"truth": truth, "files": files, "results": results}


def classify(entry: dict, outcome: dict) -> tuple[str, str]:
    status = outcome["status"]
    if status == "error":
        return "FAIL", "tool error"
    if status == "ok":
        figures = outcome.get("figures", {"exact": False, "problems": ["no figures"]})
        if entry["expect"] == "refuse":
            return "CRITICAL", "released a file that must be refused"
        return ("PASS", "exact") if figures["exact"] else ("CRITICAL", "; ".join(figures["problems"]))
    if outcome["code"] not in CODES:
        return "FAIL", f"untyped code {outcome['code']}"
    if entry["expect"] == "release":
        return "MISS", "refused a file expected to release"
    return "PASS", "n/a"


def report(data: dict, notes: str, path: Path) -> None:
    rows, tally = [], {}
    for entry in data["files"]:
        result = data["results"][entry["name"]]
        outcome = result["sequential"]
        verdict, detail = classify(entry, outcome)
        tally[verdict] = tally.get(verdict, 0) + 1
        expected = {"release": "release, figures equal truth", "refuse": "typed refusal", "safe": "refusal or exact release"}[entry["expect"]]
        actual = outcome["status"] if outcome["status"] != "refused" else f"refused {outcome['code']}"
        agree = len({(r.get("status"), r.get("code")) for r in result.values()}) == 1
        rows.append(f"| {entry['name']} | {entry['format']} | {entry['variant']} | {expected} | {actual} | {verdict}: {detail} | {'yes' if agree else 'NO'} |")
    released = sum(1 for e in data["files"] if data["results"][e["name"]]["sequential"]["status"] == "ok")
    truth = data["truth"]
    lines = [
        "# MCP format matrix",
        "",
        "Ground truth: opening " + truth["opening"] + " INR, " + str(len(truth["transactions"])) + " transactions, closing " + truth["closing"] + ".",
        "Every file was verified through the npm MCP server (stdio) inside the sandbox image with process_upload, records, verify_many and a parallel execute.",
        "",
        "| File | Format | Variant | Expected | Actual | Verdict | Same in verify_many and parallel |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        f"Files: {len(data['files'])}. Released: {released}. Refused: {len(data['files']) - released}.",
        "Verdicts: " + ", ".join(f"{k} {v}" for k, v in sorted(tally.items())) + ".",
        "PASS is a correct decision with exact figures. MISS is a safe refusal of a file expected to release. CRITICAL is a wrong release.",
        "",
        notes,
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def docker_drive(directory: Path) -> dict:
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    command = ["docker", "run", "--rm", "-i", "-v", f"{directory}:/fmt", "-v", f"{Path(__file__).resolve()}:/app/format_matrix.py:ro",
               "--entrypoint", "python", IMAGE, "/app/format_matrix.py", "drive", "/fmt"]
    done = subprocess.run(command, env=env, capture_output=True, text=True, timeout=3000)
    if done.returncode != 0:
        raise SystemExit(done.stderr[-4000:])
    return json.loads((directory / "results.json").read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["generate", "drive", "report", "run"])
    parser.add_argument("directory", type=Path)
    parser.add_argument("--notes", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "evidence" / "mcp_format_matrix.md")
    args = parser.parse_args()
    notes = args.notes.read_text(encoding="utf-8") if args.notes else ""
    if args.action == "generate":
        generate(args.directory)
    elif args.action == "drive":
        data = asyncio.run(drive(args.directory))
        (args.directory / "results.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    elif args.action == "report":
        report(json.loads((args.directory / "results.json").read_text(encoding="utf-8")), notes, args.out)
    else:
        generate(args.directory)
        report(docker_drive(args.directory), notes, args.out)


if __name__ == "__main__":
    main()
