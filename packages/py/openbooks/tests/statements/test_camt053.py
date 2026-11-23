"""camt.053 through the pipeline with only openbooks.statements registered: a balanced statement releases with its directions,
balances, references and descriptions; a tampered closing balance, a DTD or entity declaration, malformed XML, a non-camt file and
a missing opening balance are refused with the existing codes. Nothing here needs a PDF library or PyTorch."""
import pytest

from openbooks.core import Params, process

XML_DECL = '<?xml version="1.0" encoding="UTF-8"?>'
NS = ' xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"'
ACCT = '<Acct><Id><IBAN>DE89370400440532013000</IBAN></Id><Ccy>EUR</Ccy></Acct>'
OPBD = '<Bal><Tp><CdOrPrtry><Cd>OPBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">1000.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2025-01-01</Dt></Dt></Bal>'
CLBD = '<Bal><Tp><CdOrPrtry><Cd>CLBD</Cd></CdOrPrtry></Tp><Amt Ccy="EUR">1150.50</Amt><CdtDbtInd>CRDT</CdtDbtInd><Dt><Dt>2025-01-31</Dt></Dt></Bal>'
CREDIT = ('<Ntry><Amt Ccy="EUR">200.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2025-01-05</Dt></BookgDt>'
          '<AcctSvcrRef>REF1</AcctSvcrRef><NtryDtls><TxDtls><RmtInf><Ustrd>Invoice 42</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>')
DEBIT = ('<Ntry><Amt Ccy="EUR">49.50</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2025-01-20</Dt></BookgDt>'
         '<AddtlNtryInf>Card payment</AddtlNtryInf></Ntry>')
PENDING = ('<Ntry><Amt Ccy="EUR">999.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>PDNG</Sts><BookgDt><Dt>2025-01-30</Dt></BookgDt></Ntry>')


def statement(sid: str, opening: str, closing: str, entries: str) -> str:
    return f"<Stmt><Id>{sid}</Id>{ACCT}{opening}{closing}{entries}</Stmt>"


def document(*statements: str, ns: str = NS) -> str:
    return f'{XML_DECL}<Document{ns}><BkToCstmrStmt>{"".join(statements)}</BkToCstmrStmt></Document>'


SAMPLE = document(statement("S1", OPBD, CLBD, CREDIT + DEBIT))


@pytest.fixture
def run(tmp_path):
    def _run(text, ext="xml", **params):
        f = tmp_path / f"in.{ext}"
        f.write_text(text, encoding="utf-8")
        return process(f, Params(**params))
    return _run


def test_balanced_statement_releases_with_directions_balances_references_and_descriptions(run):
    doc = run(SAMPLE)
    assert doc["status"] == "ok" and doc["file"]["layout_version"] == "camt053.v1", doc.get("error")
    txns = doc["data"]["transactions"]
    assert [(t["direction"], t["amount"]["amount"], t["amount"]["currency"], t["date"]) for t in txns] == [
        ("credit", "200.00", "EUR", "2025-01-05"), ("debit", "49.50", "EUR", "2025-01-20")]
    assert [t["reference"] for t in txns] == ["REF1", None]
    assert [t["description"] for t in txns] == ["Invoice 42", "Card payment"]
    batch = doc["data"]["batches"][0]
    assert batch["opening"] == {"amount": "1000.00", "currency": "EUR"}
    assert batch["closing"] == {"amount": "1150.50", "currency": "EUR"}
    assert doc["evidence"][f"{txns[0]['id']}.amount"]["raw_text"] == "200.00"


def test_namespace_less_xml_releases_the_same_transactions(run):
    doc = run(document(statement("S1", OPBD, CLBD, CREDIT + DEBIT), ns=""))
    assert doc["status"] == "ok", doc.get("error")
    assert [(t["direction"], t["amount"]["amount"]) for t in doc["data"]["transactions"]] == [("credit", "200.00"), ("debit", "49.50")]


def test_two_statements_release_as_two_batches_with_their_own_balances(run):
    second = statement("S2", OPBD.replace("1000.00", "1150.50"), CLBD.replace("1150.50", "1160.50"),
                       '<Ntry><Amt Ccy="EUR">10.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2025-02-02</Dt></BookgDt></Ntry>')
    doc = run(document(statement("S1", OPBD, CLBD, CREDIT + DEBIT), second))
    assert doc["status"] == "ok", doc.get("error")
    assert [b["closing"]["amount"] for b in doc["data"]["batches"]] == ["1150.50", "1160.50"]
    assert [t["id"] for t in doc["data"]["transactions"]] == ["txn-1-00001", "txn-1-00002", "txn-2-00001"]
    assert len(doc["data"]["accounts"]) == 1


def test_unbalanced_closing_balance_is_refused_by_the_balance_gate(run):
    doc = run(SAMPLE.replace("1150.50</Amt>", "1150.51</Amt>"))
    assert doc["status"] == "refused" and doc["error"]["code"] == "BALANCE_MISMATCH"


def test_reversal_indicator_flips_the_direction_and_the_balance_must_follow(run):
    reversed_credit = CREDIT.replace("<CdtDbtInd>CRDT</CdtDbtInd>", "<CdtDbtInd>CRDT</CdtDbtInd><RvslInd>true</RvslInd>")
    flipped = run(document(statement("S1", OPBD, CLBD.replace("1150.50", "750.50"), reversed_credit + DEBIT)))
    assert flipped["status"] == "ok", flipped.get("error")
    assert flipped["data"]["transactions"][0]["direction"] == "debit"
    assert run(document(statement("S1", OPBD, CLBD, reversed_credit + DEBIT)))["error"]["code"] == "BALANCE_MISMATCH"


def test_pending_entries_are_ignored(run):
    doc = run(document(statement("S1", OPBD, CLBD, CREDIT + DEBIT + PENDING)))
    assert doc["status"] == "ok", doc.get("error")
    assert [t["amount"]["amount"] for t in doc["data"]["transactions"]] == ["200.00", "49.50"]


@pytest.mark.parametrize("declaration", ['<!DOCTYPE Document [<!ENTITY x "y">]>', '<!ENTITY x "y">'])
def test_dtd_or_entity_declaration_is_refused_as_parse_error(run, declaration):
    doc = run(SAMPLE.replace("?>", "?>" + declaration, 1))
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


def test_malformed_xml_is_refused_as_parse_error(run):
    doc = run(SAMPLE[:-30])
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"


def test_xml_that_is_not_camt053_is_refused_as_unknown_layout(run):
    doc = run(f"{XML_DECL}<Invoice><Line>1</Line></Invoice>")
    assert doc["status"] == "refused" and doc["error"]["code"] == "UNKNOWN_LAYOUT"


def test_missing_opening_balance_is_refused_as_parse_error(run):
    doc = run(document(statement("S1", "", CLBD, CREDIT + DEBIT)))
    assert doc["status"] == "refused" and doc["error"]["code"] == "PARSE_ERROR"
