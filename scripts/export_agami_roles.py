"""Export weak word-role labels from digital PDFs whose extracted ledger matches the source JSON exactly."""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

from eval_agami import BASE, truth_rows
from openbooks.core.errors import Refusal
from openbooks.core.params import Params
from openbooks.statements.pdf_front import extract_statement, read_words


def export_document(pdf: Path) -> tuple[list[dict], int]:
    raw = json.loads(pdf.with_suffix(".json").read_text(encoding="utf-8"))
    expected = truth_rows(raw)
    params = Params(currency="INR", date_order="dmy", ocr=False)
    pages, method = read_words(pdf, params)
    data, evidence, _, _ = extract_statement(pages, params, method)
    observed = data["transactions"]
    actual = [(row["date"], row["direction"], Decimal(row["amount"]["amount"]),
               Decimal(row["balance_after"]["amount"])) for row in observed]
    if not expected or actual != expected:
        return [], 0

    boxes = defaultdict(list)
    for row in observed:
        for field, role in (("date", "date"), ("amount", row["direction"]), ("balance_after", "balance")):
            loc = evidence[f"{row['id']}.{field}"]
            if loc["page"] is not None and loc["bbox"] is not None:
                boxes[loc["page"]].append((loc["bbox"], role))

    output = []
    for words in pages:
        if not words:
            continue
        page = words[0].page
        tokens = []
        for word in words:
            roles = {role for (x0, y0, x1, y1), role in boxes[page]
                     if x0 <= word.cx <= x1 and y0 <= word.cy <= y1}
            tokens.append({"text": word.text, "bbox": [word.x0 / word.pw, word.y0 / word.ph,
                                                       word.x1 / word.pw, word.y1 / word.ph],
                           "role": roles.pop() if len(roles) == 1 else None})
        output.append({"document": f"{pdf.parent.name}/{pdf.name}", "page": page,
                       "label_source": "agami_json_exact_row_match_plus_parser_geometry", "tokens": tokens})
    return output, len(observed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=BASE / "India_Bank_Statement_Digital_Type2")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    files = sorted(args.data.glob("*.pdf"))
    if not files:
        parser.error("no PDF files found")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    stats = Counter(input_files=len(files))
    roles = Counter()
    with args.out.open("w", encoding="utf-8") as target:
        for pdf in files:
            try:
                pages, rows = export_document(pdf)
            except Refusal as refusal:
                stats[refusal.code] += 1
                continue
            if not pages:
                stats["row_mismatch"] += 1
                continue
            stats.update(files=1, pages=len(pages), transactions=rows)
            for page in pages:
                roles.update(token["role"] or "unlabeled" for token in page["tokens"])
                target.write(json.dumps(page, ensure_ascii=False) + "\n")
    if not stats["files"]:
        parser.error("no source ledgers matched exactly")
    print(json.dumps({"export": dict(stats), "role_tokens": dict(roles)}, indent=2))


if __name__ == "__main__":
    main()
