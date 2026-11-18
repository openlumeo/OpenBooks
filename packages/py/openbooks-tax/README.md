# openbooks-tax

Providers for tax and ledger documents, registered with `openbooks-core`. **All layouts are experimental**: they follow public
descriptions of the documents, not real exports, and have only been exercised on synthetic fixtures.

| Layout | What proves it |
|---|---|
| `tds_26as.v1` (Form 26AS) | printed totals of amount, tax deducted, tax deposited |
| `ais.v1` (Annual Information Statement) | printed total of reported value |
| `fira.v1` (inward remittance advice) | foreign amount x rate = INR amount within 0.01, INR - charges = net credited, printed totals |
| `form_1099b.v1` (Form 1099-B detail) | proceeds - cost basis + adjustment = gain or loss on every row, printed totals. Other 1099 forms have no arithmetic to prove and are not parsed. |
| `trial_balance.v1` | debits = credits, printed totals |

A layout is released only when the document supplies a figure of its own to check. A printed total that is an Excel formula is not independent evidence.

Currency: 26AS and AIS assume INR and 1099-B assumes USD when `--currency` is not given (the document does not state one). FIRA states its own currencies. Numeric dates in 26AS, AIS and FIRA are read day-first; 1099-B refuses unless the order is provable from the file or given with `--date-order`.

```bash
pip install openbooks-tax          # brings openbooks-core
python -m openbooks_core run form26as.csv --machine
```
