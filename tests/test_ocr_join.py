"""OCR repair of amounts whose decimal point was dropped (Courier-style fonts)."""
from openbooks.pdf_front import Word, _join_split_amounts


def line(*texts, y=10.0, gap=3.0, w=20.0):
    out, x = [], 0.0
    for t in texts:
        out.append(Word(t, x, y, x + w, y + 8, 1, 0.9))
        x += w + gap
    return out


def texts(ws):
    return sorted(w.text for w in ws)


def test_rejoins_dropped_point():
    assert texts(_join_split_amounts(line("ATM", "764", "72"))) == ["764.72", "ATM"]


def test_rejoins_comma_split_thousands():
    assert texts(_join_split_amounts(line("10", ",", "034", "14"))) == ["10,034.14"]
    assert texts(_join_split_amounts(line("17,122", "43"))) == ["17,122.43"]


def test_does_not_swallow_a_reference_number():
    assert texts(_join_split_amounts(line("297756", "764", "72"))) == ["297756", "764.72"]


def test_leaves_dates_and_far_apart_tokens_alone():
    assert texts(_join_split_amounts(line("01", "Jan", "2026"))) == ["01", "2026", "Jan"]
    assert texts(_join_split_amounts(line("764", "72", gap=200.0))) == ["72", "764"]
    assert texts(_join_split_amounts(line("01", "12"))) == ["01", "12"]
