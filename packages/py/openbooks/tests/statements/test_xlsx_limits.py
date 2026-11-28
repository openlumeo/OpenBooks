import struct
import zipfile
from decimal import Decimal

import pytest

openpyxl = pytest.importorskip("openpyxl")

from openbooks.core import Params, process  # noqa: E402
from openbooks.core.frontends import xlsx  # noqa: E402

HEAD = ["Date", "Narration", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"]
ROWS = [["01/01/2026", "Salary", None, 500.0, 1500.0], ["02/01/2026", "Rent", 200.5, None, 1299.5], ["03/01/2026", "Coffee", 4.5, None, 1295.0]]
P = Params(currency="INR", opening=Decimal("1000.00"), date_order="dmy")
SHEET = "xl/worksheets/sheet1.xml"
CENTRAL_HEADER = b"PK\x01\x02"


def workbook(path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Statement"
    for r in [HEAD, *ROWS]:
        ws.append(r)
    wb.save(path)
    return path


def understate_directory(path, name, declared_size):
    data = bytearray(path.read_bytes())
    at = data.find(CENTRAL_HEADER)
    while at != -1:
        name_length = struct.unpack_from("<H", data, at + 28)[0]
        if bytes(data[at + 46 : at + 46 + name_length]) == name.encode():
            struct.pack_into("<I", data, at + 24, declared_size)
        at = data.find(CENTRAL_HEADER, at + 4)
    path.write_bytes(bytes(data))
    return path


def test_a_member_whose_directory_understates_its_size_is_refused_and_never_read_past_it(tmp_path):
    src = workbook(tmp_path / "s.xlsx")
    with zipfile.ZipFile(src) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    lying = tmp_path / "lying.xlsx"
    with zipfile.ZipFile(lying, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in parts.items():
            z.writestr(name, data + (b" " * (8 * 1024 * 1024) if name == SHEET else b""))
    understate_directory(lying, SHEET, 100)
    doc = process(lying, P)
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNSUPPORTED_INPUT"
