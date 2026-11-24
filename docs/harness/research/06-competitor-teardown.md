# 06 Competitor Teardown: financial-document parsing and verification

Status: research only. No code changes.
Accessed: 2026-11-24 (all URLs fetched or searched that day). Vendor pages rarely show a publication date; none is claimed here.
Size: L (18 vendors, cross-checked pricing and integrations).

## Labels used

- VERIFIED: stated on a page fetched or searched on 2026-11-24. The URL is cited.
- VENDOR CLAIM: a marketing or self-reported figure. Not independently checked.
- INDEPENDENT: third-party or reproducible evidence. None was found for this teardown beyond blog posts, so it is marked where used.
- HYPOTHESIS: an inference from the evidence. Confidence is given.
- UNVERIFIED: a number or claim that could not be confirmed from a primary source. Not used in decisions.

## Ranked shortlist (what to act on first)

1. Balance-proof verification as a deterministic, local check (opening balance plus transactions equals closing balance; totals reconcile; typed refusal when they do not). No vendor reviewed advertises this as a product. HYPOTHESIS, confidence medium-high. Benchmark: a synthetic statement corpus with planted errors, measuring refusal precision and recall.
2. Local-first open-source parsing (Docling MIT, Marker Apache-2.0 code, MinerU Apache-2.0-derived) combined with Open Books' own verifier. Lowers cost to zero for the default path. Gap is the verifier, not the parser. Confidence medium.
3. MCP plus skills for agents with bring-your-own OCR keys. Reducto, Docling, and several community Mistral and Azure servers already ship MCP. Owning the combination of MCP, BYO keys and refusal is differentiated, but not unique. Confidence medium.

## Comparison table

Pricing numbers are list prices from the cited page. "n/s" means not stated on the page.

| Vendor | Positioning | Pricing (VERIFIED unless noted) | Open source | Strengths (vendor or verified) | Known weaknesses | Verification / reconciliation | MCP / agent |
|---|---|---|---|---|---|---|---|
| LlamaParse / LlamaIndex | Commercial parsing API; LiteParse is a separate local parser | Pay-as-you-go $0 + 10,000 credits/mo, then $1.50 per 1,000 credits. Fast 1 credit/page; Cost-effective 3; Agentic 10; Agentic Plus 25. Layout +3 credits/page. [llamaindex.ai/pricing](https://www.llamaindex.ai/pricing) | LlamaParse commercial; LiteParse open source (license n/s). [same page](https://www.llamaindex.ai/pricing) | Tiered modes; cached re-parse free. VENDOR CLAIM: Agentic Plus ranks first on ParseBench. | Credit model makes per-document cost hard to predict (third-party blog, not primary). The `llama_parse` repo is archived and deprecated in favour of `llama-cloud` ([github](https://github.com/run-llama/llama_parse)); the page's two dates conflict. | None. Balance check not mentioned. | Claude marketplace connector listed in search results (not fetched) [claude.com](https://claude.com/marketplace/connectors/llamaparse). Blog on MCP returned 404: UNVERIFIED. |
| Reducto | Enterprise document pipeline (parse, extract, split, classify, edit) | Standard: $150 free usage, then pay-as-you-go. r-1 Parse $10/1k pages; r-1 mini $1/1k; Extract $20/1k; Deep Extract $40/1k. Batch -20% (calculator). Enterprise: VPC/on-prem, custom. [reducto.ai/pricing](https://reducto.ai/pricing) | No (license n/s on MCP page) | Citations on extraction (`citations` option adds source references per field) [docs](https://docs.reducto.ai/mcp-server); VPC/on-prem offered | Costs stack per operation (Parse + Extract billed separately). Customer complaints: none found; UNVERIFIED | Field-level citations only. No balance proof on pricing or MCP page. | Official MCP: parse, extract, split, classify, edit, upload; stdio and HTTP; hosted at mcp.reducto.ai does not read local files [docs.reducto.ai/mcp-server](https://docs.reducto.ai/mcp-server) |
| Unstructured | Document ETL for RAG/agents; "Transform" API | 10,000 free pages, then $0.015/page. Audio $0.015/min; video $0.045/min [unstructured.io/pricing](https://unstructured.io/pricing) | Yes, library; license Apache-2.0 [github](https://github.com/Unstructured-IO/unstructured). Paid "Transform v2" is the higher-quality tier. | Open source library free "will stay completely free"; vendor claims 2x table accuracy and 58% less invented content vs. OSS (VENDOR CLAIM, 224-page test). | Vendor-run benchmarks only. Complaints: none found; UNVERIFIED | None. | "Transform (MCP / API)" product nav; MCP details not on page. Partner integration with Anthropic listed [pricing page](https://unstructured.io/pricing) |
| Docling (IBM / docling-project) | Open-source document conversion toolkit | Free (MIT) [github](https://github.com/docling-project/docling) | Yes, MIT, ~71k stars | Broad formats (PDF, DOCX, XLSX, HTML, audio, email, images); local. Tech report: typical table takes 2-6 s on CPU, depends on cell count [arXiv 2408.09869](https://arxiv.org/html/2408.09869v1) | Complex/irregular merged cells remain open (third-party blog test, single run; UNVERIFIED as general). Tracker has open table bugs (#1680, #1653; titles only seen). | None. Extraction only. | Official MCP server (`docling-mcp`), local by default; can delegate to docling-serve [docs](https://docling-project.github.io/docling/usage/mcp/) |
| Marker (Datalab) | PDF/Office to Markdown/JSON, LLM-assisted | Code Apache-2.0; weights under modified OpenRAIL-M, free for research, personal use and startups under $5M funding/revenue; commercial use via contact [github](https://github.com/datalab-to/marker) | Code yes; weights restricted | v2.0.0 reads text layer first and calls VLM only for scanned pages, equations, low-confidence tables [PyPI/release notes via search, UNVERIFIED direct fetch] | Hallucination concern raised on HN; benchmark judged by LLM (critique, not a bug report) [HN via search]. Specific table-hallucination issue: not found | None | None found |
| MinerU (OpenDataLab) | PDF to structured output, multi-tier (Flash to Pro) | Not stated on page; CLI, SDK, HTTP API. Hosted tier pricing UNVERIFIED | Yes, "MinerU Open Source License, based on Apache 2.0 with additional conditions" [github](https://github.com/opendatalab/MinerU) | Qualitative accuracy claims for formulas and cross-page tables; links OmniDocBench | No accuracy numbers on page. Chinese-first docs (UNVERIFIED) | None | No MCP found; installable `mineru` agent skill and CLI with `--json` [github](https://github.com/opendatalab/MinerU) |
| Mistral OCR | OCR API, also self-hostable open-weight models | Per 1,000 pages; exact price NOT captured (UNVERIFIED). Batch processing -50% [mistral.ai/pricing](https://mistral.ai/pricing) | Open-weight models Apache-2.0 for research/individual use; commercial needs Mistral license [same page] | Self-host option; batch discount | Commercial self-host needs separate license | None | Community MCP servers only (e.g. lemopian/mistral-ocr-mcp, [PyPI](https://pypi.org/project/iflow-mcp-lemopian-mistral-ocr/)); no official MCP found |
| Azure AI Document Intelligence | Enterprise cloud OCR and prebuilt models | Prices blank on the cached page (UNVERIFIED). Free tier 500 pages/mo (Free-Web/Container). Bank statement model not listed on page. [azure.microsoft.com](https://azure.microsoft.com/en-us/pricing/details/document-intelligence/) | No | Enterprise compliance; custom models; training free for first 10 hrs neural | Price opacity on cached page. | None | No official MCP found; third-party `@kaenova/document-intelligence-mcp` [pkgstats](https://www.pkgstats.com/pkg:@kaenova/document-intelligence-mcp) |
| AWS Textract | Cloud OCR and document analysis | Per page, US West (Oregon). DetectDocumentText $0.0015 first 1M pages; Tables $0.015; Forms $0.05; AnalyzeExpense $0.01; AnalyzeLending $0.07. Free tier 3 months [aws.amazon.com/textract/pricing](https://aws.amazon.com/textract/pricing/) | No | Low per-page price for raw OCR; mature | Cost stacks when combining Forms+Tables+Queries ($0.07). No financial verification. | None | No Textract-specific MCP; AWS MCP Server is generic [AWS](https://aws.amazon.com/about-aws/whats-new/2025/11/aws-mcp-server) |
| Google Document AI | Cloud OCR and processors | Prices NOT captured (UNVERIFIED). | No | Unknown from primary source (UNVERIFIED) | Unknown | Unknown | Unknown (UNVERIFIED) |
| Veryfi | OCR API for receipts, invoices, bank docs | Free 100 docs/mo. Starter $500/mo credits; bank documents $0.25/doc; receipts $0.08; invoices $0.16. Billed per document (up to 15 pages) [veryfi.com/pricing](https://www.veryfi.com/pricing/) | No | Per-document pricing; bank statements OCR API from Starter | Reconciliation not mentioned | Not offered (page silent) | Not mentioned |
| Nanonets | Document AI workflows and agents | Starter free with $50 credits, then $100/mo for 100 credits; Growth and Enterprise custom. Simple run $0.02; standard AI $0.10; complex AI $0.30 per run [nanonets.com/pricing](http://nanonets.com/pricing) (https redirected) | No | Block-based pricing; free start | Bank statements and MCP not on pricing page | Not offered (page silent) | "Nanonets Agents" product listed; details not given |
| Klippa (Doxis AI.dp) | OCR and IDP, especially EU enterprise | Annual license or pay-per-document; custom quote. Pricing page 404 (UNVERIFIED). [klippa.com/en/ocr](https://www.klippa.com/en/ocr/) | No | Bank statement OCR listed; SDK for mobile; vendor claim "up to 99%" accuracy | Pricing opaque | Not offered | Not mentioned |
| Extend | Developer IDP with Parse, Split, Classify, Extract, Edit, Verify | Pay-as-you-go: 10k credits ($100) free, then $0.01 per credit. Parse Light $2/1k pages, Performance $10/1k; Extract Performance 3 credits/page; Verify Standard $30/1k, Agentic $40/1k + $0.35/doc [extend.ai/pricing](https://www.extend.ai/pricing) | No | Verify step exists; per-mode pricing | Verify is LLM-level validation, not balance arithmetic (HYPOTHESIS from page wording) | Partial: "Verify" endpoint (semantic, not balance) | Not mentioned on page |
| Rossum | Enterprise invoice/AP automation | Starter from $18,000/yr; Business/Enterprise by quote [rossum.ai/pricing](https://www.rossum.ai/pricing/) | No | Enterprise AP workflows | High entry price | Not offered | Not mentioned |
| Plaid Statements (and Docupipe) | Plaid: bank-branded PDF copy of statements. Docupipe: document extraction. | Plaid: billed per statement when Item created; exact price via sales [plaid.com/docs/statements](https://plaid.com/docs/statements/). Docupipe: pricing tiers not captured (UNVERIFIED) [docupipe.ai/pricing](https://docupipe.ai/pricing) | No | Plaid: authoritative bank-branded PDF, up to 2 years, US depository accounts | Plaid: PDF only, no parsed data per the page; US only | Plaid: not mentioned. Docupipe: not mentioned | Not mentioned |
| Ocrolus | Lender-focused document analytics (bank statements, pay stubs, tax docs) | Not disclosed; "outcome-based unit economics" [ocrolus.com](https://www.ocrolus.com/) | No | Lender workflows; "regulatory-grade data capture and fraud detection"; income and cash-flow analysis | Sales-gated; lender vertical | Fraud and income analytics, not balance proof per page (HYPOTHESIS: the closest to statement verification, medium confidence) | MCP not mentioned; developer API and docs exist |
| Mindee | Developer document API with prebuilt models | Starter $44/mo monthly or $529/yr; Pro $116/mo; 1 page = 1 credit; overage at unit rate +20% [mindee.com/pricing](https://www.mindee.com/pricing) | No | Clear unit pricing; developer SDKs | Bank statement listed only as a document type; no product detail on page | Not offered | MCP not mentioned |

## Complaints (GitHub, HN, Reddit)

Searches for user complaints returned almost no primary complaint threads. Vendor docs, release notes and third-party blogs dominated. Marked UNVERIFIED where absent.

- LlamaParse: no user complaint thread found. Pricing-model confusion is in third-party blogs only (UNVERIFIED as a user complaint).
- Docling: open table-related issues exist (#1680, #1653 titles only). No bank-statement-specific issue found.
- Marker: HN critique of LLM-judged benchmark (methodology, not a bug). No table-hallucination issue found.
- Reducto, Unstructured, MinerU, Mistral, Azure, Textract, Google, Veryfi, Nanonets, Klippa, Extend, Rossum, Plaid, Docupipe, Ocrolus, Mindee: no complaint sources found in this pass. UNVERIFIED.

Next step for complaints: search GitHub issues with "bank statement", "balance", "table", "hallucinat" for each open-source repo; search Reddit r/Rag and r/LocalLLaMA.

## Verification and reconciliation (balance proof)

- No reviewed vendor advertises balance-proof verification (opening + transactions = closing; totals reconcile) as a product.
- Closest: Extend Verify (semantic validation, page wording), Ocrolus (fraud and income analytics), Veryfi (bank statement OCR only). None cite balance arithmetic.
- Plaid Statements gives a bank-branded PDF copy, which is a source document, not a verification.
- Reducto citations give field-level source references, which supports provenance but not arithmetic proof.

## MCP and agent integrations

- Official MCP: Reducto (verified), Docling (verified, local), LlamaParse marketplace connector (search result only).
- Community MCP only: Mistral OCR, Azure Document Intelligence, Textract (via Activepieces).
- No MCP mentioned: Unstructured (nav only), MinerU (CLI and skill), Veryfi, Nanonets, Klippa, Extend, Rossum, Plaid, Ocrolus, Mindee.

## Where the gap is: three whitespace positions Open Books can honestly own

1. Deterministic balance proof with typed refusal. Every financial document returns either balance-proven JSON or a typed refusal with the failing check named. Evidence: no reviewed vendor sells this; closest tools are semantic (Extend Verify) or analytics (Ocrolus). Confidence: medium-high (HYPOTHESIS). Proposed benchmark: synthetic statements with planted errors (wrong sign, dropped row, shifted decimal, wrong period), scored on refusal recall and false refusal rate.
2. Local-first verification on top of free open-source parsing. Docling and Marker run locally and are free (verified), but none verifies totals. Open Books can use Tesseract by default and keep statements on the user's machine. Evidence: Docling MIT, local MCP (verified). Confidence: medium. Benchmark: end-to-end cost and latency per statement on CPU with and without a cloud OCR fallback.
3. Agent-native verification with bring-your-own OCR keys. Reducto and Docling already ship MCP. The unclaimed combination is an MCP tool and skill that returns a refusal or proof, routes to the user's own key (Mistral, Textract, Azure) only when Tesseract fails, and reports cost per document. Evidence: Reducto MCP tools (verified), Mistral and Azure community MCPs only. Confidence: medium. Benchmark: agent task success on a fixed set of synthetic statements, comparing answer-with-proof against answer-without.

## Open questions (UNVERIFIED)

- Mistral OCR per-page price and whether batch -50% applies to OCR.
- Google Document AI per-page prices and bank statement processor.
- Azure per-1,000-page prices and whether a bank statement model exists.
- Docupipe pricing tiers and reconciliation features.
- Marker's current table accuracy in issues.
- Reddit and GitHub user complaints for most vendors.

## Sources

- https://www.llamaindex.ai/pricing
- https://github.com/run-llama/llama_parse
- https://claude.com/marketplace/connectors/llamaparse
- https://reducto.ai/pricing
- https://docs.reducto.ai/mcp-server
- https://unstructured.io/pricing
- https://github.com/Unstructured-IO/unstructured
- https://github.com/docling-project/docling
- https://docling-project.github.io/docling/usage/mcp/
- https://arxiv.org/html/2408.09869v1
- https://github.com/datalab-to/marker
- https://github.com/opendatalab/MinerU
- https://mistral.ai/pricing
- https://pypi.org/project/iflow-mcp-lemopian-mistral-ocr/
- https://azure.microsoft.com/en-us/pricing/details/document-intelligence/
- https://www.pkgstats.com/pkg:@kaenova/document-intelligence-mcp
- https://aws.amazon.com/textract/pricing/
- https://aws.amazon.com/about-aws/whats-new/2025/11/aws-mcp-server
- https://www.veryfi.com/pricing/
- http://nanonets.com/pricing
- https://www.klippa.com/en/ocr/
- https://www.extend.ai/pricing
- https://www.rossum.ai/pricing/
- https://plaid.com/docs/statements/
- https://docupipe.ai/pricing
- https://www.ocrolus.com/
- https://www.mindee.com/pricing
