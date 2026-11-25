# Open Books: keyword and question research (END USERS and DEVELOPERS)

Date: 2026-11-23. Method: 30 WebSearch queries (standard mode), results read from the returned link lists and snippets. Ranking is the order returned by search, not rank tracking. No search volumes are shown: **volume unknown** for every query, because no cited tool reported volume. People Also Ask and autocomplete were NOT observed directly (the search tool does not return them), so those queries are derived from seed terms and marked UNVERIFIED. Open Books / Lumeo did not appear in any result set (see Gap note at end).

## Ranking summary (relevance x winnability)

| Rank | Cluster | Intent | Relevance | Winnability | Score |
|---|---|---|---|---|---|
| 1 | C1 AI agents and MCP for statements | Developer / comparison | High | High | Top |
| 2 | C2 Arithmetic and integrity checks | Informational / how-to | High | High | Top |
| 3 | C3 CAMT.053 / MT940 / OFX parsing | Developer / informational | High | High | High |
| 4 | C4 Parse statements in Python / Node | Developer how-to | High | High | High |
| 5 | C5 Bank statement to Tally | Transactional / troubleshooting | Medium-High (India) | Medium-High | High |
| 6 | C6 Indian bank-specific extraction (HDFC, SBI, ICICI, Axis) | Transactional / how-to | High | Medium-High | High |
| 7 | C7 Conversion failures (password, scanned) | Troubleshooting | Medium | High | Medium-High |
| 8 | C8 PDF to Excel / CSV / JSON (consumer) | Transactional | High | Low | Medium |
| 9 | C9 Bank statement OCR API | Commercial / developer | High | Low-Medium | Medium |
| 10 | C10 Safety of uploading statements | Informational | Medium | Medium | Medium |
| 11 | C11 Loan underwriting analyzers | Commercial | Medium | Low | Low-Medium |
| 12 | C12 Bank reconciliation software | Commercial | Medium | Low | Low |

---

## C1. MCP servers and AI agents for statements and finance (rank 1)

- **Searcher:** developer building an AI agent; accounting firm or fintech evaluating MCP; Claude/ChatGPT user wanting to read a statement.
- **Queries (8):**
  1. AI agent read bank statement MCP
  2. MCP server for accounting finance AI agents
  3. bank statement MCP server Claude
  4. MCP server parse camt.053 statement
  5. MCP bank statement parser open source
  6. how to let Claude read bank statement PDF
  7. MCP server for bookkeeping Claude Code (UNVERIFIED, derived)
  8. financial data MCP server security read-only (UNVERIFIED, derived)
- **Current top pages (as returned):**
  - https://www.docuclipper.com/integrations/mcp/bank-statements/ (vendor product page, MCP, 14-day trial)
  - https://pypi.org/project/camt053-mcp/ (PyPI package, developer)
  - https://socket.dev/pypi/package/bankstatementparser-mcp (package scan page)
  - https://glama.ai/mcp/servers/sebastienrousseau/bankstatementparser-mcp (directory listing)
  - https://github.com/elcukro/bank-mcp (GitHub, live bank connector, read-only)
  - https://www.cpapracticeadvisor.com/2026/10/20/financial-cents-rolls-out-mcp-server-for-accounting-firms/192046 (trade news)
  - https://www.digits.com/blog/mcp (vendor blog)
  - https://www.bakertilly.com/insights/sage-intacct-mcp-server-finance-leaders (consultancy blog)
  - https://memo.bank/en/product/mcp/ (vendor product)
- **Gap we can win:** Almost all results are either vendor news or small PyPI/GitHub packages with no guide. Nobody in the top set compares "file-based statement MCP" (read a PDF or CAMT/MT940 file, return validated JSON) against "live bank connector MCP", and none explains the verification step (balances and totals) an agent should run before trusting output. Open Books already fits the file-based slot.
- **Best format:** Docs-style MCP setup page per client (Claude Desktop, Claude Code, ChatGPT), plus a comparison table, plus a JSON output schema page.

## C2. Arithmetic and integrity checks on statements and invoices (rank 2)

- **Searcher:** bookkeeper, lender analyst, AP clerk, developer validating extracted data.
- **Queries (8):**
  1. verify bank statement arithmetic opening closing balance
  2. verify financial document arithmetic invoice totals check
  3. how to check extracted bank statement data is correct
  4. bank statement balance check formula
  5. detect tampered or edited bank statement PDF
  6. invoice total recalculation quantity unit price check
  7. bank statement totals mismatch debits credits what it means
  8. automated checks on OCR extracted transactions (UNVERIFIED, derived)
- **Current top pages:**
  - https://www.cpapracticeadvisor.com/?p=193997 ("5 Checks Before You Trust Extracted Bank Statement Data", trade article)
  - https://www.docuclipper.com/blog/bank-statement-verification (vendor blog)
  - https://www.docuclipper.com/docs/review-transactions-balance-and-totals-checks/ (vendor docs)
  - https://ramp.com/blog/accounts-payable/invoice-verification (vendor blog, May 2026)
  - https://tipalti.com/resources/learn/invoice-verification/ (vendor guide)
  - https://dev.to/poskono_99425db14ac67774/why-chatgpt-will-silently-lie-about-your-bank-statement-and-how-to-catch-it-13mb (developer post)
  - https://www.knime.com/use-case/incorrect-totals-detection (vendor use case)
- **Gap we can win:** Results are generic accounting advice. No top page gives a concrete, runnable check list for a statement (opening + sum(txns) = closing, running balance per row, count of rows, currency and date-order checks) with code and an explicit note that arithmetic proves consistency, not authenticity. Open Books can publish exactly this with its own verify output.
- **Best format:** Explainer with a checklist, worked numeric example, and a runnable snippet; link to a "what arithmetic cannot prove" section.

## C3. CAMT.053, MT940 and OFX parsing (rank 3)

- **Searcher:** fintech or ERP developer, treasury analyst, bank integration engineer.
- **Queries (8):**
  1. CAMT.053 MT940 OFX parsing library
  2. parse CAMT.053 python
  3. MT940 parser python
  4. camt.053 to CSV converter
  5. camt.053 to MT940 conversion
  6. OFX QFX parser python
  7. what is MT940 format explained
  8. camt.053 vs MT940 difference
- **Current top pages:**
  - https://docs.rs/crate/camt053/0.3.3 and sibling versions (Rust crate docs, developer)
  - https://pypi.org/project/bankfile/ (Python, MT940 and OFX today; CAMT.053 "next")
  - https://pypi.org/project/mt-940/ (Python MT940, many releases)
  - https://github.com/railslove/cmxl (Ruby, MT940 and MT942)
  - https://github.com/railslove/camt_parser (Ruby, basic CAMT.053)
  - https://github.com/cstuder/camt2csv and https://github.com/FreddyMeijer/CAMT053-Tools (scripts)
  - https://github.com/maptiler/iso2ofx (converter, OFX output)
  - https://packagist.org/packages/webwingscz/bank-statements (PHP, camt.053 and MT940)
- **Gap we can win:** Libraries and repos dominate; there is no single neutral format guide that compares CAMT.053, MT940 and OFX field-by-field (which field maps to which), and no page shows one schema mapped across all three. A mapping reference page with field tables is a clear gap. Note: bankfile itself says CAMT.053 is not yet written, so that claim is a differentiator.
- **Best format:** Reference doc (field mapping table per format), plus a "convert between formats" how-to, plus a JSON schema page.

## C4. Parse bank statements in Python and Node (rank 4)

- **Searcher:** developer building a finance feature or script.
- **Queries (8):**
  1. parse bank statement python library
  2. extract transactions from PDF python pdfplumber
  3. bank statement parser node.js
  4. bank statement to pandas dataframe
  5. python bank statement parser regex per bank
  6. parse bank statement PDF open source GitHub
  7. bank statement API node.js SDK (UNVERIFIED, derived)
  8. pdftotext bank statement parsing tutorial (UNVERIFIED, derived)
- **Current top pages:**
  - https://pypi.org/project/bankstatementparser (PyPI, reads CSV, OFX, QFX, MT940, CAMT)
  - https://github.com/sebastienrousseau/bankstatementparser (GitHub, CLI and streaming)
  - https://pypi.org/project/parse-bank-statements/ (German banks only)
  - https://pypi.org/project/bankstatements-core/ (PDF parsing)
  - https://levelup.gitconnected.com/creating-a-bank-statement-parser-with-python-9223b895ebae (Medium-hosted tutorial)
  - https://huggingface.co/Ranjit0034/finance-entity-extractor (HF repo, pdfplumber plus regex per bank, Indian banks)
  - https://dev.to/oddshop/how-to-automate-bank-statement-imports-with-python-50af (dev.to tutorial)
- **Gap we can win:** Packages are thin and several list only one country. A maintained, multi-bank Python and Node guide with a published schema, a test fixture set and a "bring your own bank" recipe is missing. Open Books has a Python lib and an npm CLI, so the page can be a real side-by-side install and parse example.
- **Best format:** Docs tutorial (install, parse, output JSON), with a per-language tab and a runnable repo link.

## C5. Bank statement to Tally (rank 5, India)

- **Searcher:** Indian accountant or CA, Tally user, small business owner.
- **Queries (8):**
  1. bank statement to Tally import converter
  2. how to import bank statement in Tally Prime from PDF
  3. convert PDF bank statement to Tally XML
  4. Tally bank reconciliation import Excel
  5. Tally bank statement import not a valid format
  6. bank statement Excel to Tally import template
  7. auto reconcile bank statement Tally
  8. import HDFC SBI statement into Tally (UNVERIFIED, derived)
- **Current top pages:**
  - https://help.tallysolutions.com/bank-recon/bank-statement/ (vendor docs, official)
  - https://tallysolutions.com/tally/how-to-get-pdf-bank-statements-into-tally-without-converters-or-manual-entry/ (vendor blog)
  - https://taxguru.in/finance/bank-statement-import-excel-tally.html (Indian tax portal)
  - https://www.caclubindia.com/experts/t-pri-6-0-import-bk-stat-in-excel-xslx-csv-csd-says-invalid-format-2954924.asp (CA forum, error thread)
  - https://www.sourceforge.net/projects/excel-to-tally-bank-statements/ (free tool)
  - https://excel2tally.freshdesk.com/... (vendor support article)
  - https://ai.icai.org/usecases_details.php?id=185 (ICAI use case)
- **Gap we can win:** Tally's own help says PDF-converted files fail with "Not a valid format" and that editing the file causes the same error. Forum posts guess at date formats. A page that gives the exact header and date rules, the reconciliation-start date trap, and a "convert, validate, import" flow that avoids the error is missing. Note the official claim is clear; the date-format claim (DD/MM/YYYY) is UNVERIFIED in official docs.
- **Best format:** Troubleshooting how-to with error-message table; tie to Tally's import menu path (Alt+O, Bank Statement).

## C6. Indian bank-specific extraction: HDFC, SBI, ICICI, Axis (rank 6)

- **Searcher:** Indian individual or small-business user needing data out of a net-banking PDF; developer building for Indian banks.
- **Queries (8):**
  1. extract transactions from HDFC SBI ICICI bank statement PDF
  2. HDFC bank statement to Excel
  3. SBI bank statement PDF to Excel
  4. ICICI bank statement to CSV
  5. Axis bank statement PDF to Excel
  6. bank statement PDF parsing India
  7. HDFC bank statement to Tally (UNVERIFIED, derived)
  8. credit card statement PDF to Excel India HDFC password (UNVERIFIED, derived)
- **Current top pages:**
  - https://www.docuclipper.com/blog/convert-hdfc-bank-statement-to-excel/ (vendor per-bank page)
  - https://www.adobe.com/in/acrobat/roc/blog/credit-card-statement-password-guide.html (Adobe India blog)
  - https://www.adobe.com/in/acrobat/roc/blog/how-to-convert-bank-statement-pdf-to-excel.html (Adobe India blog)
  - https://www.terra-insight.com/insights/bank-statement-pdf-parsing-india (vendor article)
  - https://bankconv.helpscoutdocs.com/article/21-convert-pdf-to-csv (vendor help docs)
  - https://www.aiaccountant.com/resources/bank-statement-converter (converter)
  - https://huggingface.co/Ranjit0034/finance-entity-extractor (open source, HDFC, ICICI, SBI)
- **Gap we can win:** Per-bank pages exist only for HDFC from one vendor. Nobody publishes a bank-by-bank support matrix (bank, statement type, native vs scanned, password, sample header, verified date) for HDFC, SBI, ICICI and Axis, with explicit "tested on" dates. That matrix is the content gap, and it is also a trust signal.
- **Best format:** Per-bank landing pages (four) plus one matrix page; each with a sample header row and a "last verified" line.

## C7. Conversion failures: password-protected and scanned statements (rank 7)

- **Searcher:** consumer stuck on a conversion error; accountant with locked PDFs.
- **Queries (8):**
  1. bank statement PDF to Excel not working password protected
  2. unable to convert password protected PDF to excel
  3. remove password from bank statement PDF
  4. bank statement PDF to Excel blank output scanned
  5. Adobe export PDF bank statement to Excel error
  6. convert scanned bank statement to Excel OCR
  7. bank statement PDF to CSV empty rows fix (UNVERIFIED, derived)
  8. bank statement converter says file cannot be processed (UNVERIFIED, derived)
- **Current top pages:**
  - https://adobe.com/in/acrobat/roc/blog/techniques-to-access-bank-statement-pdf-with-password.html (Adobe blog)
  - https://community.adobe.com/questions-27/chase-bank-statements-are-password-protected-622158 (Adobe forum)
  - https://community.adobe.com/questions-27/i-have-the-prepaid-converter-my-password-protected-bank-statements-can-not-be-converted-to-excel-how-do-i-remove-the-password-security-620306 (Adobe forum)
  - https://www.docuclipper.com/docs/upload-problems-and-errors/ (vendor docs)
  - https://exceldemy.com/forum/threads/get-data-from-password-protected-pdf-bank-statement.301/post-1269 (forum)
- **Gap we can win:** Forum answers are "print to PDF" workarounds of uncertain legality and reliability. A clear, honest guide on what an owner may do (use the bank's own CSV or Excel export, ask the bank for an unlocked copy, use an on-device unlock), what Open Books does with a password (where it is supplied, and that it is not stored), and what error means what.
- **Best format:** Troubleshooting FAQ with error-to-fix table; schema-marked FAQ.

## C8. PDF bank statement to Excel, CSV or JSON, consumer (rank 8)

- **Searcher:** individual or small business needing a spreadsheet from a statement.
- **Queries (8):**
  1. convert bank statement PDF to Excel
  2. convert bank statement PDF to CSV
  3. bank statement PDF to JSON
  4. free bank statement converter
  5. how to convert bank statement to excel
  6. bank statement to Google Sheets
  7. bank statement to QuickBooks QBO converter
  8. bank statement converter online safe (UNVERIFIED, derived)
- **Current top pages:**
  - https://www.adobe.com/in/acrobat/roc/blog/how-to-convert-bank-statement-pdf-to-excel.html (Adobe blog)
  - https://smallpdf.com/blog/how-to-convert-bank-statements-from-pdf-to-csv (vendor blog)
  - https://docparser.com/blog/pdf-bank-statement-to-excel/ (vendor blog)
  - https://www.veryfi.com/ocr-tools/bank-statement-pdf-to-excel/ (vendor tool)
  - https://parseur.com/convert/bank-statement/to-json (vendor tool)
  - https://medium.com/nanonets/convert-pdf-bank-statements-to-excel-62c892afee9c (Medium)
  - https://workspace.google.com/marketplace/app/bank_statement_converter/44730854792 (Google Workspace add-on)
- **Gap we can win:** Crowded and commercial. The angle that is not taken: the only tool here that outputs verified JSON with an arithmetic check result, plus a free tier. Expect long-tail wins only.
- **Best format:** Tool landing page with a try-it box and a how-to for each output format.

## C9. Bank statement OCR API (rank 9)

- **Searcher:** developer or startup building document intake (fintech, lending, expense tools).
- **Queries (8):**
  1. bank statement OCR API
  2. bank statement data extraction API
  3. bank statement OCR API pricing per page
  4. Azure Document Intelligence bank statement model
  5. bank statement API JSON transactions
  6. Mindee bank statement API
  7. Veryfi bank statement API
  8. LlamaParse bank statement extraction (UNVERIFIED, derived)
- **Current top pages:**
  - https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/prebuilt/bank-statement (vendor docs)
  - https://mindee.com/product/bank-statement-ocr (vendor product)
  - https://www.veryfi.com/bank-statements-ocr-api (vendor product)
  - https://docs.veryfi.com/api/bank-statements/process-a-bank-statement (API docs)
  - https://www.docuclipper.com/api-docs/bank-statement-ocr-api/ (API docs)
  - https://www.llamaindex.ai/services/bank-statement-ocr (vendor product)
  - https://docs.mindee.com/models/pricing (pricing docs)
- **Gap we can win:** Big vendors own it. The gap is a neutral, developer-first comparison with real cost per 100 pages (vendor pricing differs: Mindee's sources disagree, e.g. $0.05 to $0.10 per page or EUR 0.044 per credit), plus accuracy measured on Indian statements, which no top page reports.
- **Best format:** Comparison table with dated pricing and methodology; API quickstart.

## C10. Is it safe to upload bank statements (rank 10)

- **Searcher:** consumer worried about privacy; accountant deciding on a tool.
- **Queries (8):**
  1. is it safe to upload bank statements online
  2. are bank statements safe to share
  3. should I redact bank statement before sending
  4. do bank statement converters store my data
  5. bank statement upload privacy
  6. how to securely share bank statements
  7. bank statement converter no login required (UNVERIFIED, derived)
  8. does Open Books store uploaded statements (UNVERIFIED, derived)
- **Current top pages:**
  - https://pdf.net/blog/are-bank-statements-safe-to-share (vendor blog)
  - https://xodo.com/blog/how-to-securely-share-pdf-bank-statements (vendor blog)
  - https://statementdecoder-web.onrender.com/blog/is-it-safe-to-upload-bank-statement (small vendor)
  - https://www.usbank.com/financial-education/secure/is-online-banking-safe.html (bank education page)
  - https://www.nbc.ca/en/business/help-centre/transactions/digital-deposit/documents-safety.html (bank help page)
- **Gap we can win:** Vendor blogs sell PDF tools. Nobody publishes a data-handling statement with specifics (where processing runs, retention window, whether files train models, whether a bank login is needed). Open Books can publish that as a verifiable page, linked from every upload screen.
- **Best format:** Trust/security explainer with a plain data-flow diagram and a retention table.

## C11. Bank statement analyzer for loan underwriting (rank 11)

- **Searcher:** lender, NBFC, fintech underwriter, mortgage broker.
- **Queries (8):**
  1. bank statement analyzer for loan underwriting
  2. automated bank statement analysis software
  3. bank statement analysis API lending India
  4. bank statement analysis DTI income calculation
  5. bank statement fraud detection lending
  6. Account Aggregator bank statement India API
  7. bank statement analyzer for self-employed income (UNVERIFIED, derived)
  8. Ocrolus alternative (UNVERIFIED, derived)
- **Current top pages:**
  - https://www.docuclipper.com/solutions/bank-statement-analysis/ (vendor solution)
  - https://www.ocrolus.com/blog/automating-bank-statement-analysis/ (vendor blog)
  - https://inscribe-marketing-mirror.inscribe.ai/solution-explorer/bank-statement-analyzer (vendor)
  - https://www.biz2x.com/how-a-bank-statement-analyzer-should-work/ (vendor blog)
  - https://research.finbox.in/blog/bank-statement-analysis-api-loan-underwriting-india/ (vendor research)
  - https://arya.ai/blog/ai-powered-bank-statement-analysis-mortgage-underwriting (vendor blog)
  - https://api.rebit.org.in (official AA API specs, India)
- **Gap we can win:** Enterprise vendors; low fit for an open tool unless it targets developers. The AA (Account Aggregator) angle is a real gap for India: no top page explains how file-based parsing and AA-sourced data differ for a lender. Lower priority.
- **Best format:** Explainer on file-based vs AA data, linked to a developer page.

## C12. Bank reconciliation software (rank 12)

- **Searcher:** finance team, SMB owner, controller.
- **Queries (8):**
  1. automatic bank statement reconciliation software
  2. bank reconciliation software for small business
  3. reconcile bank statement automatically
  4. Xero bank reconciliation
  5. QuickBooks bank reconciliation
  6. Oracle automatic reconciliation rules
  7. bank reconciliation tool India GST (UNVERIFIED, derived)
  8. reconcile bank statement with invoices script (UNVERIFIED, derived)
- **Current top pages:**
  - https://www.xero.com/my/accounting-software/reconcile-bank-transactions/ (vendor)
  - https://www.sage.com/en-us/sage-business-cloud/accounting/features/bank-reconciliation/ (vendor)
  - https://docs.oracle.com/en/cloud/saas/financials/25d/faofc/automatic-reconciliation.html (vendor docs)
  - https://agicap.com/en-us/article/bank-reconciliation-software/ (vendor)
  - https://www.techrepublic.com/es/article/best-bank-reconciliation-software/ (review, "2026")
- **Gap we can win:** Very low. Incumbents dominate. Only a developer angle (reconciliation rules as a library call, via the Python or npm package) is realistic. Otherwise skip or link out.
- **Best format:** Developer tutorial only; do not compete on consumer queries.

---

## Gap note

Open Books and Lumeo did not appear in any of the 30 result sets. Search-result share is currently zero for branded and category queries, so the first step is indexation and a crawlable product page on the category terms above. The page `openbooks.openlumeo.com` itself was not fetched in this run.

## 20-page content plan

| # | Slug | Title | Target query | Format |
|---|---|---|---|---|
| 1 | /mcp-bank-statement-server | Bank statement MCP server for Claude and AI agents | AI agent read bank statement MCP | Docs (setup per client) |
| 2 | /mcp-vs-bank-connector | MCP file parser vs live bank connector: which to use | MCP server for accounting finance AI agents | Comparison |
| 3 | /verify-bank-statement-arithmetic | How to verify bank statement arithmetic | verify bank statement arithmetic opening closing balance | Explainer + checklist |
| 4 | /verify-financial-document-arithmetic | Verify invoice and statement arithmetic, and what it cannot prove | verify financial document arithmetic | Explainer |
| 5 | /camt053-field-mapping | CAMT.053 field reference | CAMT.053 MT940 OFX parsing library | Reference table |
| 6 | /mt940-vs-camt053-vs-ofx | MT940 vs CAMT.053 vs OFX: which format and why | camt.053 vs MT940 difference | Comparison |
| 7 | /camt053-to-csv | Convert CAMT.053 to CSV locally | camt.053 to CSV converter | How-to (tool + script) |
| 8 | /parse-bank-statement-python | Parse bank statements in Python | parse bank statement python library | Docs tutorial |
| 9 | /parse-bank-statement-nodejs | Parse bank statements in Node.js | bank statement parser node.js | Docs tutorial |
| 10 | /bank-statement-to-tally | Import a bank statement into Tally (step by step) | bank statement to Tally import converter | How-to |
| 11 | /tally-not-a-valid-format | Fix "Not a valid format" in Tally bank import | Tally bank statement import not a valid format | Troubleshooting FAQ |
| 12 | /hdfc-bank-statement-to-excel | HDFC bank statement PDF to Excel and JSON | HDFC bank statement to Excel | Per-bank landing |
| 13 | /sbi-bank-statement-to-excel | SBI bank statement PDF to Excel and JSON | SBI bank statement PDF to Excel | Per-bank landing |
| 14 | /icici-bank-statement-to-csv | ICICI bank statement to CSV | ICICI bank statement to CSV | Per-bank landing |
| 15 | /axis-bank-statement-to-excel | Axis bank statement PDF to Excel | Axis bank statement PDF to Excel | Per-bank landing |
| 16 | /indian-bank-support-matrix | Indian bank statement support matrix (tested dates) | bank statement PDF parsing India | Matrix |
| 17 | /password-protected-bank-statement | Converting a password-protected bank statement | bank statement PDF to Excel not working password protected | Troubleshooting FAQ |
| 18 | /is-it-safe-to-upload-bank-statement | Is it safe to upload bank statements (our data handling) | is it safe to upload bank statements online | Trust explainer |
| 19 | /bank-statement-ocr-api-comparison | Bank statement OCR API comparison with cost per 100 pages | bank statement OCR API | Comparison table |
| 20 | /bank-statement-to-json | Bank statement to JSON: schema and example | bank statement PDF to JSON | Docs + schema |

Note: Pages 12 to 15 need the per-bank test fixtures before publishing, or they will be thin. Page 2 and page 19 need dated, sourced pricing and must not repeat vendor marketing claims.
