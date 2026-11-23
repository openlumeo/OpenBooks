# Samples

Each file was run through the Open Books engine with `process_upload` (for the CSVs, opening balance `1000.00`, currency INR, date order dmy).

| File | Expected outcome |
|---|---|
| `statement_balanced.csv` | `status: ok` (released). Two transactions, 900.00 then 950.00 running balance, assertions pass. |
| `statement_tampered.csv` | `status: refused`, code `BALANCE_MISMATCH`. The closing balance on the second row is 960.00; the arithmetic gives 950.00. No JSON is released. |
| `camt053_balanced.xml` | `status: ok` (released), detected format `camt053`. Run without an opening balance, since the statement carries its own. |
