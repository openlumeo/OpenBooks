# Open Books SEO and AEO strategy

Synthesis of docs/seo/research/01 to 06. Anything marked UNVERIFIED in those files stays unverified here.

## Position

Open Books releases a financial file as JSON only when its own arithmetic proves it, otherwise a typed refusal that names the reason. Open Books and Lumeo appeared in none of 30 sampled result sets, so the starting point is zero visibility. The differentiator to state plainly everywhere: a visible balance check, a released-only-if-balanced contract, and an MCP server for AI agents.

## Audiences, ranked

1. AI agent and MCP builders (cluster 1, most winnable, no strong incumbent): need a registry listing and a runnable quickstart.
2. Developers parsing statements in Python or Node, and CAMT.053 / MT940 / OFX formats (clusters 3 and 4): need neutral reference pages and code.
3. Indian accountants, bookkeepers and small business users (clusters 5 and 6): Tally import errors, per-bank statements, safety of uploading bank data.
4. Lenders and underwriters: Account Aggregator is preferred, statement parsing is the fallback; say how both fit.

## Rules from the research

- Target Google first (about 98% of India search per StatCounter June 2026, UNVERIFIED primary), then Bing, which also feeds DuckDuckGo, Copilot and ChatGPT search. Verify in Search Console and Bing Webmaster Tools.
- Do not script Google sitemap pings or the Google Indexing API. IndexNow covers Bing, Yandex, Seznam and Naver only.
- FAQPage and HowTo rich results are effectively gone. Write answer-first prose for citation, do not add FAQ markup for rich results. Keep Organization, WebSite, SoftwareApplication, BreadcrumbList and SoftwareSourceCode JSON-LD.
- llms.txt shows no measured citation effect in three vendor studies. Keep it as a docs index, do not invest further.
- Allow search bots: OAI-SearchBot, Claude-SearchBot, PerplexityBot. Perplexity-User and ChatGPT-User may ignore robots.txt. Training bots (GPTBot, ClaudeBot, Google-Extended, Applebot-Extended) are currently allowed on purpose for an open-source product.
- Third-party presence drives AI citation: MCP registries, GitHub, awesome lists, Reddit, Stack Overflow, dev.to. These need human accounts and are drafted, not posted.

## Facts rule

No claim about supported banks, retention, residency, accuracy or pricing unless the repo proves it. Pages state only what code or existing docs prove, and a gap is left out rather than invented.

## Workstreams

A. Metadata and structured data fixes on existing pages.
B. Existing docs: descriptions, thin pages, broken schema links.
C. New pages: reference and quickstart content from the 20-page plan that the repo can fully support.
D. Autopilot: IndexNow on deploy, CI SEO checks, JSON-LD and metadata validation.
E. Distribution drafts: registry, awesome list, Show HN, dev.to, READMEs.

## Manual steps that need the owner

Search Console and Bing Webmaster verification, npm publish of `@lumeo_hq/openbooks-mcp` 0.2.3 with `mcpName` set, MCP Registry publish with mcp-publisher, posting launches, and setting the INDEXNOW_KEY repository secret.
