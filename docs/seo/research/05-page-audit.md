# 05 Page audit: public pages of the Open Books web app

Read-only audit. Scope: `web/app` routes and every page in `web/content/docs` (21 pages). Word counts are estimates from `wc -w`, which includes frontmatter and code, so they run high. Rendered title = `<title> | Open Books` (`web/app/layout.tsx:13`, template), except the home page, which uses `absolute`.

## Global facts

- Site URL `https://openbooks.lumeo.co.in` (`web/lib/site.ts:3`).
- `pageMetadata()` sets canonical, OG and Twitter from `path` (`web/lib/site.ts:5-29`).
- Root description is about 230 characters, over the 160 limit (`web/app/layout.tsx:14-15`). Pages without their own description inherit it.
- `robots.ts` disallows `/api/` and `/auth/` for all bots, including AI crawlers (`web/app/robots.ts:4-5`).
- `/app` is `noindex` (`web/app/app/page.tsx:6`) and is missing from the sitemap (`web/app/sitemap.ts:7-10` lists only `/` and docs).
- The sitemap includes every docs page via `docs.getPages()` (`web/app/sitemap.ts:8`).
- No FAQ, glossary, changelog, status, pricing or security page exists under `web/app` or `web/content`.
- `public/schema/` is empty, but `content/docs/output-contract.mdx` links to `/schema/openbooks.v1.schema.json` and `.refusal.schema.json` (broken links).

## Marketing and app routes

| URL | Title (source) | Meta description | H1 | Words | JSON-LD | Inbound / outbound links | Answer-first | Issues |
|---|---|---|---|---|---|---|---|---|
| `/` | "Open Books by Lumeo", absolute (`web/app/(marketing)/page.tsx:20`) | Set, 136 chars (`page.tsx:16-17`) | "Every figure proven, or refused with a reason." (`web/components/landing/hero.tsx:12-14`) | Not measured, est. 500-800 across sections | SoftwareApplication, `page.tsx:43-54` | In: sitemap, footer. Out: `/docs`, `/app`, `/docs/model`, `/llms.txt` (`web/components/landing/site-footer.tsx`) | Partial. Hero is a claim, not a question. The description says what the product does; visible copy does not name the file types. | Brand-only title with no query; H1 is a slogan; no FAQ; no supported-format list above the fold; section H2s are claims ("Confidence is not evidence.", `reframe.tsx:18`) |
| `/app` | "Workspace | Open Books" (`web/app/app/page.tsx:5`) | None | Not verified (`components/workspace`) | Not verified | Not in sitemap; `noindex` | n/a (app tool) | No description; correct to keep out of index |
| `/auth/sign-in` | Inherits "Open Books by Lumeo" (`web/app/layout.tsx:13`) | Inherits root, over 160 (`layout.tsx:14`) | "Welcome back" (`web/components/auth/auth-form.tsx:71`) | ~100 | None | In: footer? no; Out: `/auth/sign-up` | n/a | Duplicate title with home; no metadata export; crawl-blocked by robots (`robots.ts:5`) |
| `/auth/sign-up` | Inherits "Open Books by Lumeo" | Inherits root | "Create your account" (`auth-form.tsx:71`) | ~120 | None | Out: `/auth/sign-in` (`auth-form.tsx:14`) | n/a | Same as sign-in; contains a "training phase" data statement (`auth-form.tsx:101`) that belongs on a privacy page |

## Developer docs routes

Shared template: `web/app/(developers)/docs/[...slug]/page.tsx` and `web/components/docs/article.tsx`.
- Title and description come from frontmatter (`article.tsx:9-17`). H1 is `DocsTitle` (`article.tsx:48`). `text/markdown` alternate is added (`article.tsx:22`).
- Breadcrumb JSON-LD has position 1 "Developer docs" pointing at the **home URL**, not `/docs` (`article.tsx:43-46`). Fix this.
- No FAQPage, no FAQ sections, no breadcrumb visible in the UI.
- Title lengths are all 46-49 rendered characters, which pass the 60 limit.
- Descriptions under 120 characters: build-an-importer (113), cli (111), python (116), pdf-and-ocr (118), node (119), model (119). Descriptions over 160: none (mcp is 154).
- No `<img>` in any docs page. Images: not checked beyond docs content.

| URL (`/docs/...`) | Title (frontmatter) | Desc chars | Words (est.) | Code blocks | Inbound (docs, approx) | Outbound | Issues |
|---|---|---|---|---|---|---|---|
| `/docs` (index.mdx) | Open Books Developer Documentation | 140 | 649 | 0 | Global nav | 13 incl. `/llms.txt` | Title repeats brand; WebSite JSON-LD only (`article.tsx:34-38`) |
| architecture | Architecture and verification | 138 | 456 (thin) | 1 | ~1 (python) | 4 | Thin; no direct answer to "how is it verified" |
| bank-statements | Bank statements | 144 | 547 | 1 | ~4 | 4 | Title is vague; target "bank statement parser API" |
| build-an-importer | Build a bank statement importer | 113 (short) | 647 | 3 | ~2 | 3 | Short description; links `/examples/statement.csv` (exists) |
| cli | CLI commands and exit codes | 111 (short) | 651 | 2 | ~2 | 2 | Short description |
| engine-api | Self-hosted HTTP API | 131 | 763 | 4 | ~6 | 3 | Title lacks product term |
| formats | Supported formats and layouts | 133 | 540 | 0 | ~5 | 3 | Strongest target for "supported banks and formats"; no bank list |
| installation | Install Open Books | 123 | 627 | 7 | ~9 | 3 | OK |
| mcp | MCP for AI agents | 154 | 1105 | 7 | ~5 | 3 | Long; split into MCP quickstart |
| model | Model-assisted document checks | 119 (short) | 496 | 1 | ~3 | 2 | Short description; title jargon |
| node | Node.js and TypeScript | 119 (short) | 780 | 2 | ~2 | 4 | Short description; no npm install title |
| output-contract | JSON output contract | 126 | 567 | 3 | ~6 | 5 | Broken `/schema/*.json` links |
| payment-settlements | Payment settlements | 124 | 464 (thin) | 1 | ~2 | 6 | Thin; no competitor or use-case context |
| pdf-and-ocr | Bank PDFs and OCR | 118 (short) | 585 | 2 | ~4 | 5 | Short description |
| python | Python API | 116 (short) | 500 | 2 | ~4 | 4 | Short description; title lacks product term |
| quickstart | Verify your first bank statement | 132 | 648 | 4 | ~6 | 3 | Good answer-first structure |
| refusals | Refusals and execution errors | 123 | 528 | 0 | ~6 | 6 | Refusal codes are a glossary in disguise; no code sample |
| tax-and-workpapers | Tax documents and workpapers | 124 | 439 (thin) | 1 | ~1 (index) | 5 | Thin; orphaned from docs nav except index |
| test-an-integration | Test a document integration | 134 | 696 | 1 | ~2 | 6 | OK |
| troubleshooting | Troubleshooting | 122 | 483 | 1 | ~4 | 3 | Generic title |
| workspace | Use the browser workspace | 132 | 452 (thin) | 0 | ~1 (index) | 5 | Thin; no code; orphan-ish; best candidate for "bank statement to Excel" |

Heading hierarchy: docs bodies start at `##` under the fumadocs H1, which is fine. `mcp.mdx:32` and `build-an-importer.mdx:41` use `#` only inside code blocks.

## Proposed metadata (per page)

| Page | Target query / intent | New title (under 60 with suffix) | New description (120-160) | H1 | Structured data |
|---|---|---|---|---|---|
| `/` | Open Books bank statement JSON; brand | "Bank statement to verified JSON | Open Books" (absolute) | Keep slogan, add visible subhead naming file types | SoftwareApplication (keep), Organization, WebSite |
| `/docs` | developer docs for document extraction | "Developer docs for bank statement parsing" | "Turn bank statements, settlements and tax files into verified JSON. Start with a sample, then integrate via CLI, Python, Node.js, HTTP or MCP." (~140) | "Developer documentation" | TechArticle + WebSite |
| `/docs/quickstart` | bank statement to JSON quickstart | "Bank statement to JSON quickstart" | Keep, add file type | "Verify your first bank statement" | TechArticle, BreadcrumbList (fixed) |
| `/docs/installation` | install openbooks python npm | "Install openbooks: Python and npm" | "Install the Open Books engine and npm wrappers, add OCR and model support, verify engine discovery." | "Install Open Books" | TechArticle, SoftwareApplication |
| `/docs/python` | bank statement python parser | "Python bank statement parser API" | Expand to ~130 chars, name the Python package | "Python API" | TechArticle |
| `/docs/node` | bank statement parser npm nodejs | "Node.js bank statement parser (npm)" | Expand to ~130 chars | "Node.js and TypeScript" | TechArticle, SoftwareApplication |
| `/docs/cli` | openbooks CLI | "Open Books CLI: commands and exit codes" | Expand to ~130 chars | "CLI commands and exit codes" | TechArticle |
| `/docs/mcp` | MCP server bank statements | "Open Books MCP server for AI agents" | Trim to under 160 | "MCP for AI agents" | TechArticle; split out "MCP quickstart" |
| `/docs/formats` | supported bank statement formats | "Supported bank statement formats (CSV, OFX, MT940, PDF)" | Keep | "Supported formats and layouts" | TechArticle, add ItemList if a formats table |
| `/docs/pdf-and-ocr` | bank statement PDF OCR | "Bank statement PDF to JSON with OCR" | Expand to ~130 | "Bank PDFs and OCR" | TechArticle |
| `/docs/refusals` | parser refusal codes | "Refusal codes and retry guidance" | Keep | "Refusals and execution errors" | TechArticle, add DefinedTermSet if a glossary |
| `/docs/workspace` | bank statement to Excel, browser | "Convert bank statements to Excel in your browser" | Keep, name Excel export only if the product supports it (verify) | "Use the browser workspace" | HowTo (text only), TechArticle |
| `/auth/sign-in` | (none, utility) | "Sign in | Open Books" | Short, no description needed | none |
| `/auth/sign-up` | (none, utility) | "Create account | Open Books" | Short | none |
| `/app` | (none, tool) | "Workspace | Open Books" | Keep `noindex` | none |

Apply FAQPage only where a visible FAQ section is added. Google restricts FAQ rich results, so treat it as a content aid.

## Pages that should exist but do not

1. **Pricing and limits.** `formats.mdx:27` has input limits, but no pricing source exists in the repo. Needs a product decision before writing.
2. **Security and privacy.** Only a one-line data statement in `auth-form.tsx:101`. A `/security` and `/privacy` page is needed.
3. **Supported banks and formats.** `formats.mdx` covers layouts but no bank list page. A `/formats/[bank]` set would target specific queries.
4. **Comparison / alternatives.** None exists. Needs competitor research (see `docs/evidence/`).
5. **End-user use-case pages.** Bank statement to Excel, JSON, Tally. None exists, and no Tally support is documented in the reviewed files.
6. **Changelog.** Release versions exist but there is no changelog page.
7. **Status page.** None.
8. **MCP quickstart and npm quickstart.** Covered inside long pages (`mcp.mdx` 1105 words, `node.mdx`). Split into dedicated pages.
9. **FAQ.** None.
10. **Glossary.** Terms such as "release", "refusal", "evidence" are defined inline only.
11. **Missing schema files.** Publish `public/schema/openbooks.v1*.json` or fix the links in `output-contract.mdx`.

## Top gaps (by impact)

1. Root description and brand-only titles (`/`, `/auth/*`, `/docs` index) with no query targeting.
2. Breadcrumb JSON-LD points to home, not `/docs` (`article.tsx:44`).
3. No pricing, security or privacy page.
4. No end-user use-case pages (bank statement to Excel/JSON).
5. Six short descriptions under 120 characters; several thin pages under 500 words.
6. Broken `/schema/*.json` links (`output-contract.mdx`).
7. `/app` and `/auth` missing titles and descriptions.
8. No FAQ, glossary or changelog.
