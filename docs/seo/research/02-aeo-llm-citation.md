# AEO / GEO research: how AI systems choose and cite sources (2025-2026)

Scope: Open Books by Lumeo (openbooks.openlumeo.com). Method: 8 web searches. Only search snippets were read; no page was fetched in full. Anything not confirmed in a snippet is marked UNVERIFIED. Vendor studies are labelled as such.

Evidence grades: **A** = official vendor or platform documentation; **B** = independent study with stated method; **C** = vendor/blog claim or folklore.

## 1. Crawlers and user agents

| Operator | Token(s) | Purpose | robots.txt | Source |
|---|---|---|---|---|
| OpenAI | GPTBot | Training | Honoured (documented) (A) | https://developers.openai.com/api/docs/bots |
| OpenAI | OAI-SearchBot | ChatGPT search index | Honoured; blocking removes you from ChatGPT search answers, navigational links may still appear; ~24h to take effect (A/secondary) | https://developers.openai.com/api/docs/bots |
| OpenAI | ChatGPT-User | User-initiated fetch | Reported as not governed by robots.txt after a Dec 2025 doc change (secondary, UNVERIFIED against current doc) | https://ppc.land/openai-revises-chatgpt-crawler-documentation-with-significant-policy-changes/ |
| OpenAI | OAI-AdsBot | Ad landing-page validation | Reported added Apr 2026 (UNVERIFIED) | https://dev.to/searchless_ai/oai-adsbot-openais-dedicated-ad-crawler-and-what-it-means-for-your-landing-pages-9fk |
| Anthropic | ClaudeBot | Training | Honoured; block = excluded from future training (A) | https://support.claude.com/en/articles/8896518-robots-txt-controls |
| Anthropic | Claude-SearchBot | Search indexing | Honoured (A) | https://support.claude.com/en/articles/8896518-robots-txt-controls |
| Anthropic | Claude-User | User-initiated fetch | Sources disagree; Anthropic states bots honour robots.txt, but one reading says Claude-User is not distinguished (UNVERIFIED) | https://support.claude.com/en/articles/8896518-robots-txt-controls |
| Perplexity | PerplexityBot | Index | Honoured per docs; IP list published (A) | https://docs.perplexity.ai/docs/resources/perplexity-crawlers.md |
| Perplexity | Perplexity-User | User-initiated fetch | Perplexity docs say generally ignores robots.txt because a user requested it (A, via docs) | https://docs.perplexity.ai/guides/perplexitybot |
| Perplexity | (undeclared agents) | Stealth crawling | Cloudflare reports rotating UAs, changing ASNs, and ignoring robots.txt (B, vendor-observed) | https://blog.cloudflare.com/perplexity-is-using-stealth-undeclared-crawlers-to-evade-website-no-crawl-directives/ |
| Google | Googlebot | Search, and AI Overviews/AI Mode use the Search index | Honoured | UNVERIFIED in this session (no official page fetched) |
| Google | Google-Extended | robots.txt token only (not a crawler) for Gemini training and grounding opt-out; does NOT control AI Overviews | Token honoured (C, secondary) | https://searchengineland.com/google-extended-crawler-432636 |
| Apple | Applebot-Extended | Training opt-out token; blocking standard Applebot removes Siri/Spotlight surfaces | Honoured per Apple, secondary (C) | https://cside.com/blog/how-to-block-applebot-extended |
| Microsoft | Bingbot | Search. No separate robots.txt token for AI training found; NOARCHIVE meta cited as training opt-out (C) | UNVERIFIED | none authoritative found |
| Brave | Leo | No crawler info found | UNVERIFIED | none found |
| Microsoft Copilot | (Bing) | Uses Bing index | UNVERIFIED | none found |

Practical reading: for citation visibility, the bots that matter are the search/index bots (OAI-SearchBot, Claude-SearchBot, PerplexityBot, Bingbot, Googlebot). Training bots (GPTBot, ClaudeBot, Google-Extended, Applebot-Extended) are a separate decision. Do not block user-fetch agents expecting it to hide you; they may not obey robots.txt.

## 2. How each system selects and cites sources

- ChatGPT search: retrieves from the OAI-SearchBot index plus live fetches (ChatGPT-User). Wikipedia is over-represented in ChatGPT citations in a Rankscale.ai study of 8,000 citations (B/C) https://searchengineland.com/how-to-get-cited-by-ai-seo-insights-from-8000-ai-citations-455284
- Perplexity: favours review and expert/industry sites in the same Rankscale study (B/C), same source.
- Google AI Overviews/AI Mode: built on Google's index. Google states normal SEO ranking is the path; no special markup or AI files are needed (secondary: https://searchengineland.com/google-says-normal-seo-works-for-ranking-in-ai-overviews-and-llms-txt-wont-be-used-459422). Google-Extended does not control it.
- Claude, Copilot, Brave Leo: citation selection mechanics UNVERIFIED in this session. Brave Leo and Copilot retrieval details were not found.
- Academic framing (B): separate citation selection from citation absorption (arXiv 2604.25707, https://arxiv.org/html/2604.25707). Retrieval rank and source authority drive selection; a 2026 paper on what drives citations is at https://arxiv.org/pdf/2610.15033 (not read in full).

## 3. llms.txt and llms-full.txt

Evidence against measurable effect:
- SE Ranking study, ~300k domains: no statistically significant link between llms.txt and citation rate (B, vendor study): https://www.searchenginejournal.com/llms-txt-shows-no-clear-effect-on-ai-citations-based-on-300k-domains/561542/
- Search Atlas, 13,911 domains vs 83,387 LLM visibility records: adoption does not predict citation; apparent effect explained by domain authority (B, vendor): https://searchatlas.com/blog/limits-of-llms-txt-for-ai-search-citation-study/
- Ahrefs, 137k sites: the great majority of llms.txt files are never read by AI bots (B, vendor): https://ahrefs.com/blog/llmstxt-study/
- Optimizely: four studies; AI crawlers almost never fetch it (one test: 84 requests out of 62,100+ AI bot visits) (B, vendor): https://www.optimizely.com/field-notes/articles/does-llms-txt-work/
- Google: does not endorse or use it for Search or AI Overviews (A/secondary): https://www.seroundtable.com/google-does-not-endorse-llms-txt-40789.html ; Google's guide states Search does not use such files: https://searchengineland.com/google-says-llms-txt-files-wont-harm-or-help-your-search-rankings-480264

Evidence for: none found that a major answer engine reads llms.txt for citation decisions. Adoption figures conflict (0.3% to 28%) because methods differ. Treat llms.txt as a cheap doc index for coding agents (see section 5), not as an AEO lever.

## 4. Structured data, format, freshness, third parties

- FAQPage: Google stopped showing FAQ rich results (reported stop date 7 May 2026; secondary sources, UNVERIFIED against official page). Schema still valid markup but no SERP benefit. https://developers.google.com/search/docs/appearance/structured-data/faqpage ; background https://developers.google.com/search/blog/2023/08/howto-faq-changes
- HowTo: visible rich results narrowed in 2023 (A, Google blog). No 2026 change found.
- SoftwareApplication, Organization, SoftwareSourceCode: no Google or AI-platform doc found saying these change citation. Effect on AI citation: UNVERIFIED / folklore. Use for entity clarity; do not expect citation lift.
- Answer-first formatting, freshness, stats/citations: supported by the GEO literature directionally (arXiv 2610.15033 and vendor studies), but magnitudes are not reliable from snippets. Treat as UNVERIFIED for magnitude.
- Third parties: multiple studies (Semrush June 2025, Peec AI 30M sources, Meltwater Oct 2026 with 88.6M citations) find Reddit, Wikipedia, YouTube, LinkedIn among the most cited domains. Leaders differ by platform. Figures are vendor-reported (C). Sources: https://searchengineland.com/ai-search-engines-cite-reddit-youtube-and-linkedin-most-study-473138 ; https://www.meltwater.com/en/blog/ai-search-visibility-report-october-2026 (not read in full).

## 5. Developer assistants and package discovery

- Context7: community-maintained docs index. Libraries are added via web form (context7.com/add-library) or API `POST /v2/add/llmstxt` taking an llms.txt / llms-full.txt URL with a bearer token (A for API): https://context7.com/docs/api-reference/add-library/add-an-llmstxt-file . Repo PR route described in a third-party README only (UNVERIFIED).
- Cursor, Claude Code, Copilot discovery of packages and MCP servers: no authoritative source found in this session. Expect: README and npm/PyPI metadata (description, keywords, repository) and MCP registry listings. UNVERIFIED.
- Registries: the product already ships npm, PyPI and an MCP server.json (packages/js/mcp/server.json). Registry metadata is a concrete lever; the official MCP registry format was not verified here.

## 6. Measuring AI visibility

- Manual prompt panel: 30-50 buyer prompts (e.g. "verify financial document tampering open source", "MCP server for PDF bank statement verification"), run weekly across ChatGPT search, Claude, Perplexity, Gemini, Copilot, Brave Leo; log mention, citation URL, position, and competitor set. Method is the default for a small product; no vendor needed.
- Log-based: count hits from OAI-SearchBot, Claude-SearchBot, PerplexityBot, Googlebot, and referrers from chat.openai.com, perplexity.ai, claude.ai, copilot.microsoft.com, in server logs or the CDN.
- Vendor tools (examples seen in results): Peec AI, Meltwater, Rankscale.ai, Semrush AI toolkit. Pricing and accuracy UNVERIFIED.

## 7. Twelve ranked actions for Open Books

1. Allow OAI-SearchBot, Claude-SearchBot, PerplexityBot and Bingbot in robots.txt; check the current `web/app/robots.ts` output for accidental blocks.
2. Decide per training bot (GPTBot, ClaudeBot, Google-Extended, Applebot-Extended) and write it down; do not use these to hide from answers.
3. Make the top 10 pages answer-first: one-sentence definition, then specifics, then proof (verification steps, sample output).
4. Put exact, dated facts and benchmark numbers from the repo's own benchmarks (docs/evidence) on the pages, with the commit or date.
5. Keep the GitHub repo README and the npm and PyPI READMEs as the canonical product description; mirror the same wording on the site.
6. Earn third-party mentions on the channels the studies name (Reddit threads in r/ fintech and r/MachineLearning where disclosed, GitHub topics, Stack Overflow answers, Wikipedia only if notability is real). Disclose affiliation; no astroturfing.
7. Publish llms.txt and llms-full.txt as a developer doc index (low cost), and submit the URL to Context7; do not claim it improves citations.
8. Drop FAQPage rich-result work; keep Organization and SoftwareApplication JSON-LD accurate with version and offers; add SoftwareSourceCode to the GitHub-linked pages.
9. Verify MCP registry and package metadata (description, keywords, repository, server.json) on npm, PyPI and the MCP registry; consistent names across all three.
10. Build a 30-prompt AI visibility panel and run it weekly across ChatGPT, Claude, Perplexity, Gemini, Copilot and Brave Leo; store results in docs/seo/research.
11. Add referrer and bot-hit tracking for the search bots and AI referrers in the server or CDN logs; report monthly.
12. Re-run this research in 90 days, specifically re-checking Brave Leo, Copilot and Claude retrieval docs, and the ChatGPT-User and FAQ claims, which are secondary-sourced here.

## Gaps (not verified in this session)

Brave Leo and Copilot crawler strings; Google's official AI features and structured data page; Googlebot and Bingbot official docs; Cursor/Claude Code/Copilot discovery mechanics; the content of the Semrush, Peec, Rankscale and Meltwater studies beyond snippets.
