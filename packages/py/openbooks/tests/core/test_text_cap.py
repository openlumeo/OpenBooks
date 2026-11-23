import pytest

from openbooks.core import guard
from openbooks.core.errors import Refusal


def test_text_file_over_cap_is_refused_but_document_is_not(tmp_path, monkeypatch):
    monkeypatch.setattr(guard, "MAX_TEXT_BYTES", 4)
    text = tmp_path / "big.csv"
    text.write_bytes(b"12345")
    pdf = tmp_path / "big.pdf"
    pdf.write_bytes(b"12345")
    with pytest.raises(Refusal, match="text file is over the 64 MB limit"):
        guard.check_input(text)
    guard.check_input(pdf)
