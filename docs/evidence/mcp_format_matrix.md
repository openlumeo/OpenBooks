# MCP format matrix

Ground truth: opening 1000.00 INR, 8 transactions, closing 38708.21.
Every file was verified through the npm MCP server (stdio) inside the sandbox image with process_upload, records, verify_many and a parallel execute.

| File | Format | Variant | Expected | Actual | Verdict | Same in verify_many and parallel |
|---|---|---|---|---|---|---|
| csv_hdfc_style.csv | csv | csv_hdfc_style | release, figures equal truth | ok | PASS: exact | yes |
| csv_hdfc_style_tampered.csv | csv | csv_hdfc_style tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| csv_generic_debit_credit.csv | csv | csv_generic_debit_credit | release, figures equal truth | ok | PASS: exact | yes |
| csv_generic_debit_credit_tampered.csv | csv | csv_generic_debit_credit tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| csv_indian_commas.csv | csv | csv_indian_commas | release, figures equal truth | ok | PASS: exact | yes |
| csv_indian_commas_tampered.csv | csv | csv_indian_commas tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| csv_signed_amount.csv | csv | signed amount | release, figures equal truth | refused UNKNOWN_LAYOUT | MISS: refused a file expected to release | yes |
| csv_signed_amount_tampered.csv | csv | signed amount tampered | typed refusal | refused UNKNOWN_LAYOUT | PASS: n/a | yes |
| statement.sta | sta | clean | release, figures equal truth | ok | PASS: exact | yes |
| statement_tampered.sta | sta | tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| statement.mt940 | mt940 | clean | release, figures equal truth | ok | PASS: exact | yes |
| statement_tampered.mt940 | mt940 | tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| statement.ofx | ofx | clean | release, figures equal truth | ok | PASS: exact | yes |
| statement_tampered.ofx | ofx | tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| statement.qfx | qfx | clean | release, figures equal truth | ok | PASS: exact | yes |
| statement_tampered.qfx | qfx | tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| statement_camt053.xml | camt053 | clean | release, figures equal truth | ok | PASS: exact | yes |
| statement_camt053_tampered.xml | camt053 | tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| statement_text_dates.xlsx | xlsx | text dates | release, figures equal truth | ok | PASS: exact | yes |
| statement_real_dates.xlsx | xlsx | datetime cells | release, figures equal truth | ok | PASS: exact | yes |
| statement_text_dates_tampered.xlsx | xlsx | text dates tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| statement_text.pdf | pdf-text | clean | release, figures equal truth | ok | PASS: exact | yes |
| statement_text_tampered.pdf | pdf-text | tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| scan_printed.png | png-scan | printed | release, figures equal truth | ok | PASS: exact | yes |
| scan_printed.pdf | pdf-scan | printed | release, figures equal truth | ok | PASS: exact | yes |
| scan_printed_skewed.jpg | jpg-scan | printed skewed 1.2deg noisy | release, figures equal truth | refused PARSE_ERROR | MISS: refused a file expected to release | yes |
| scan_printed_tampered.png | png-scan | printed tampered | typed refusal | refused BALANCE_MISMATCH | PASS: n/a | yes |
| handwritten_ink_free.jpg | jpg-handwritten | ink_free clean | refusal or exact release | refused UNKNOWN_LAYOUT | PASS: n/a | yes |
| handwritten_ink_free_altered_totals.jpg | jpg-handwritten | ink_free altered totals | typed refusal | refused UNKNOWN_LAYOUT | PASS: n/a | yes |
| handwritten_segoe_print.jpg | jpg-handwritten | segoe_print clean | refusal or exact release | refused UNKNOWN_LAYOUT | PASS: n/a | yes |
| handwritten_segoe_print_altered_totals.jpg | jpg-handwritten | segoe_print altered totals | typed refusal | refused PARSE_ERROR | PASS: n/a | yes |

Files: 31. Released: 13. Refused: 18.
Verdicts: MISS 2, PASS 29.
PASS is a correct decision with exact figures. MISS is a safe refusal of a file expected to release. CRITICAL is a wrong release.

## Engine limitations found

- Signed-amount CSV (Date, Description, Amount, Balance) is refused UNKNOWN_LAYOUT; bank_csv.v1 needs separate debit and credit columns. Safe refusal, not a money error.
- A printed scan rotated 1.2 degrees with heavy noise (JPEG) is refused PARSE_ERROR. Safe refusal; the same page at 0.3 degrees releases exactly.
- Handwritten pages (Ink Free, Segoe Print, with and without altered totals) were all refused (UNKNOWN_LAYOUT or PARSE_ERROR). No wrong figures released.

## MCP layer

- No MCP-layer defect found. Uploads over 1 MiB are refused INVALID_ARGUMENTS (limit is MAX_UPLOAD_BYTES). A 9 MB verify_many request sent directly to node returns that error cleanly. The python mcp client closed the connection on multi-megabyte requests, a client-side artefact, so fixtures are kept under 1 MiB.
- Results agree across process_upload, verify_many and the parallel execute for every file.

## Commands

    python scripts/harness/format_matrix.py run <dir>

This generates fixtures into <dir> (needs Pillow, openpyxl and Windows fonts Inkfree.ttf and segoepr.ttf), drives the image openbooks-mcp-sbx over stdio with docker, and writes this report. Individual steps: generate <dir>, drive <dir> (inside the container, python with mcp installed), report <dir> --notes <file> --out <file>.

