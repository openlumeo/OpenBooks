# Search engine indexing, ranking and automation: Open Books

Scope: https://openbooks.openlumeo.com (Next.js, India-centred, global developer audience).
Status: research snapshot dated 2026-11-23. Claims are sourced from WebSearch snippets unless marked. Where a primary page was not opened, the claim is flagged UNVERIFIED. Re-check primary pages before acting.

Sizing: M (desk research, one document).

## 1. Market share (StatCounter, India, search engine)

Source: https://gs.statcounter.com/search-engine-market-share/all/india (snapshot pages vary between June and October 2026).

- All platforms, June 2026: Google 97.85%, Bing 1.15%, DuckDuckGo 0.43%, Yahoo 0.4%, Yandex 0.1%, Ecosia 0.02%.
- October 2026 snapshot: Google 98.06%, Bing 1.11%, Yahoo 0.35%, DuckDuckGo 0.33%.
- Desktop only (July 2026): Google about 95.4%, Bing about 3%.
- Mobile about 67% of search traffic, desktop about 32% (June 2026 page).

Global share for the other engines was not pulled in this pass (UNVERIFIED). Use StatCounter worldwide pages before quoting global numbers.

Implication: in India, Google is the target. Bing is the only second-tier engine that matters in volume. Baidu, Naver, Seznam and Yandex are low-priority for an India-first product unless the audience proves otherwise in analytics.

## 2. Google

### Ownership and submission
- Verify a Domain property in Search Console (DNS TXT) so http, https and subdomains are covered. URL-prefix properties are the fallback.
- Submit sitemap.xml in Search Console and reference it in robots.txt (`Sitemap: https://openbooks.openlumeo.com/sitemap.xml`).
- Sitemap limits: 50MB uncompressed or 50,000 URLs per file; use a sitemap index beyond that. Source: https://developers.google.com/search/docs/crawling-indexing/sitemaps/large-sitemaps
- lastmod must reflect real content change. Google warns against stamping every build with the current time. Source: https://developers.google.com/search/blog/2023/06/sitemaps-lastmod-ping
- Sitemap ping endpoint is retired (announced 26 June 2023); HTTP pings return 404. Do not script pings to Google. Source: https://developers.google.com/search/blog/2023/06/sitemaps-lastmod-ping

### Indexing API
- Officially restricted to JobPosting and BroadcastEvent (embedded in VideoObject). Using it for product or docs pages is outside documented scope. Source: https://developers.google.com/search/apis/indexing-api
- Default testing quota is 200 requests; more needs approval. Batch endpoint accepts up to 100 calls per request. Source: https://developers.google.com/search/apis/indexing-api/v3/using-api
- Decision: do not use the Indexing API for Open Books pages. Rely on sitemap lastmod plus internal links.

### Structured data
- FAQ rich results: restricted to government and health sites from August 2023; later notices say FAQ rich results no longer appear. FAQPage markup is still valid JSON-LD but earns no rich result for this site. Sources: https://developers.google.com/search/blog/2023/08/howto-faq-changes , https://searchenginejournal.com/google-drops-faq-rich-results-from-search (secondary)
- HowTo: removed from mobile in 2023 and reported removed from desktop in September 2025 (sources disagree on timing). Do not invest in HowTo markup. Source: https://www.searchenginejournal.com/google-completely-removes-how-to-rich-results/496479/ (secondary, UNVERIFIED on exact date)
- SoftwareApplication: no 2026 status confirmed in this pass (UNVERIFIED). Check the current Search Central structured data gallery before relying on it.
- BreadcrumbList: still a documented rich-result type in the Search Central gallery (UNVERIFIED for 2026, check gallery).
- Google said it would remove support for some structured data types from Search Console and its API starting January 2026, without a full list in the snippet read (UNVERIFIED). Check the list before adding any type.
- Rule regardless of type: JSON-LD must match visible page text, and must be validated with Rich Results Test and the Schema Markup Validator.

### AI Overviews
- AI features need no special markup. Requirement: structured data must match visible content; normal Search eligibility is the gate. Source: https://developers.google.com/search/docs/appearance/ai-features (opened via search snippet; primary page not fetched here)
- Third-party claims of a required schema type for AI Overviews conflict with this and are rejected.

### Core Web Vitals
- Targets (LCP 2.5s, INP 200ms, CLS 0.1 at the 75th percentile): UNVERIFIED in this pass. Confirm at https://web.dev/articles/vitals before setting CI budgets.

### Crawl and robots
- Googlebot follows robots.txt. Do not block CSS or JS needed for rendering. Crawl-rate control is not exposed beyond the Search Console crawl-stats report (UNVERIFIED in detail).

### Canonical and hreflang
- Use self-referencing canonical on every indexable page. Canonical must point to the preferred absolute URL (https, no trailing-slash drift).
- For en-IN: use `hreflang="en-IN"` only if India-specific content exists. Otherwise use `en` plus `x-default`. Google ignores hreflang as a ranking signal; it only selects the variant to show. Source: https://developers.google.com/search/docs/specialty/international/localized-versions (UNVERIFIED in this pass)
- Do not auto-generate hreflang for language pairs with no real translation.

## 3. Bing (Microsoft)

### Ownership and submission
- Bing Webmaster Tools can import the Search Console property, which skips separate verification. Manual setup accepts XML file, meta tag, CNAME or Domain Connect. Bing requires verification before accepting a sitemap. Source: https://bing.com/indexnow/getstarted (search snippet) and https://blogs.bing.com/webmaster/July-2025/Keeping-Content-Discoverable-with-Sitemaps-in-AI-Powered-Search
- Submit a full XML sitemap with accurate lastmod.

### IndexNow (API and ping)
- Yes, an API exists. Generate a key (8 to 128 hex chars), host `https://openbooks.openlumeo.com/<key>.txt` containing the key, then POST URL lists.
- Endpoint: `https://api.indexnow.org/indexnow` (shared) or `https://www.bing.com/indexnow`. Up to 10,000 URLs per POST. Source: https://www.indexnow.org/documentation and https://indexnow.org/faq
- Participating engines share submissions. Google does not participate. Source: https://indexnow.org/faq
- Key verification: engine fetches the key file; Yandex returns 202 until verified, then 200. Source: https://yandex.com/support/webmaster/indexnow/reference.html
- Confirm submissions in Bing Webmaster Tools under Reports & Data, IndexNow. Source: https://bing.com/indexnow/getstarted

### Copilot and ChatGPT use of Bing
- Bing Webmaster Tools has an AI Performance report (secondary source, UNVERIFIED in primary docs). Microsoft's July 2025 post says sitemaps help discovery in AI-powered search.
- How Bing's index feeds Copilot grounding and ChatGPT search: NOT verified in this pass. Do not claim a mechanism. Treat "in Bing" as the only controllable lever.

### Crawl and robots
- bingbot obeys robots.txt and Crawl-delay (UNVERIFIED in this pass; check https://www.bing.com/webmasters/help/).

## 4. DuckDuckGo

- Traditional web results come largely from Bing. DuckDuckGo runs DuckDuckBot for non-traditional results. Source: https://duckduckgo.com/duckduckgo-help-pages/results/sources
- DuckDuckGo does not accept submissions for its web index. Changes go through Bing. Source: https://duckduckgo.com/duckduckgo-help-pages/results/can-a-result-be-removed
- Action: Bing work covers DuckDuckGo. Nothing else to automate.

## 5. Brave Search

- Brave runs its own index. Source: https://brave.com/search-api-launch/ (product page; index details not read in this pass).
- Crawler user agent: Brave's help page says the crawler does not advertise a distinct user agent and follows Googlebot's robots.txt rules, so a site cannot block Brave while allowing Google. Source: https://search.brave.com/help/brave-search-crawler (via search snippet). Third-party "Bravebot" robots rules are UNVERIFIED and should not be copied.
- Goggles (custom re-ranking): create at https://search.brave.com/goggles/create and submit a hosted file. Brave fetches, validates and caches it. No documented API to submit a Goggle (community request outstanding). Hosting limits in a 2022 Register article (2MB, 10,000 rules; gist/GitHub/GitLab hosts) are dated and UNVERIFIED for 2026. Source: https://community.brave.com/t/api-to-submit-goggles/510926
- Action: nothing to submit for ranking. Only a Goggle would be a product-level choice (not required for indexing).

## 6. Yandex

- Requires a domain with its own host. Verification: HTML file in root (recommended), meta tag or DNS TXT, on Access rights page. Server must return 200 to Yandex robots. Source: https://yandex.ru/support/webmaster/service/rights.html and https://yandex.com/support/webmaster/kk/service/quick-start
- Sitemap: Sitemap files page, add URL; also declare in robots.txt. Max 50,000 links per file. Processing can take up to about two weeks. Notify icon speeds up changes. Source: https://yandex.com/support/webmaster/indexing-options/sitemap.html
- IndexNow: supported (key file verification, 202 then 200). Source: https://yandex.com/support/webmaster/indexnow/reference.html
- Per-URL recrawl control: not found (UNVERIFIED). Yandex does not guarantee all sitemap URLs appear.
- Market: 0.1% in India (StatCounter, June 2026). Low priority.

## 7. Baidu

- Requires ICP filing for mainland China hosting and ranking. Not applicable to an India-hosted site unless a China audience is targeted (UNVERIFIED; check Baidu policy).
- Verification: HTML tag in header, HTML file in root, or CNAME via Baidu Search Resource Platform. Source: https://help.aliyun.com/en/document_detail/3043763.html (third-party-hosted doc)
- Sitemap submission availability is disputed in sources (open to all vs invitation-only). Treat as UNVERIFIED; check your account.
- Robots: `User-agent: Baiduspider` (crawler UA contains "Baiduspider/2.0"; render crawler "Baiduspider-render/2.0"). Verify genuine crawler via reverse DNS to crawl.baidu.com. Source: search snippet, Baidu docs not fetched.
- Submission limits reported by a single third-party page (1000 URLs per submit, 10 per day): UNVERIFIED.
- Priority: low for India. Skip unless China is a target.

## 8. Naver (Korea)

- Register a domain or subdomain (subfolders not supported). Verify with `<meta name="naver-site-verification" content="...">` in head, then confirm ownership in dashboard. Source: third-party guides (inblog, Wix) (UNVERIFIED against Naver docs).
- Submit sitemap under Request, Submit Sitemap (sitemap.xml). Naver does not crawl new sites automatically. Source: same.
- IndexNow endpoint: `https://searchadvisor.naver.com/indexnow` (search snippet, UNVERIFIED).
- Priority: none for India or global developer audience, unless a Korean audience emerges.

## 9. Seznam (Czech)

- Seznam Webmaster: verification by meta tag or file; crawled vs indexed reports, URL inspection, reindex requests. Source: https://www.napoveda.seznam.cz/en/crawling-control (official help, partial snippet) and third-party guides.
- Sitemap in robots.txt: `Sitemap: <absolute URL>`. Source: Seznam crawling-control page.
- SeznamBot: allowed by default unless robots.txt blocks it. Source: same.
- IndexNow endpoint: `https://search.seznam.cz/indexnow` (one plugin developer reports fast crawl; anecdotal).
- Priority: none for India or global developer audience.

## 10. Ecosia

- Results come from Microsoft Bing, Google, and the EUSP European index (France and Germany), depending on region and device. Source: https://support.ecosia.org/article/579-search-results-providers
- No public submission path. Work through Bing and Google.
- Market: 0.02% in India (June 2026).

## 11. Kagi

- Own index "Teclis" (web) and "TinyGem" (news). Teclis is described as a small-web index, mostly RSS-driven (secondary sources). Source: https://help.kagi.com/kagi/search-details/search-sources.html
- Submission process for new sites: NOT found in this pass (UNVERIFIED). Kagi also uses external sources; treat as Google/Bing-adjacent.
- Relevance for developer audience: Kagi is paid and has a developer-heavy user base, so a plain well-structured page with RSS feed helps. This is a judgement, not a sourced stat.

## 12. Yahoo Search

- Yahoo results in StatCounter India: 0.35% to 0.4% (2026).
- Backend: earlier Bing partnership. Current backend in 2026 NOT verified. Do not claim it.
- No separate webmaster submission path confirmed. Treat as Bing-covered (UNVERIFIED).

## 13. Perplexity

- Two declared agents: PerplexityBot (search index) and Perplexity-User (user-initiated fetch). Source: https://docs.perplexity.ai/guides/perplexitybot and https://docs.perplexity.ai/docs/resources/perplexity-crawlers
- Perplexity states PerplexityBot will not index a site that disallows it in robots.txt. Perplexity-User generally ignores robots.txt because a user requested the fetch (per Perplexity). Third-party reports (Cloudflare, 2025) dispute Perplexity's compliance. Treat compliance as contested.
- Allow both in robots.txt for citation visibility, unless a policy decision says otherwise. Verify requests by published IP lists: https://www.perplexity.ai/perplexitybot.json and https://www.perplexity.ai/perplexity-user.json (from the crawler docs; UNVERIFIED URLs, confirm in docs).
- No submission API. Visibility depends on being crawlable and on answer-friendly content.

## 14. You.com

- YouBot: official docs at https://docs.you.com/youbot. Says it respects robots.txt including user-agent rules and crawl-delay, uses adaptive rate limiting, and sends requests from 68.67.112.0/24. robots.txt cache reported as 30 minutes.
- Contact for crawl issues: spider@you.com (from docs).
- One third-party directory says YouBot does not respect robots.txt. Treat as unverified; rely on the official docs.
- No submission API.

## 15. Ranking factors for developer-tool queries (cross-engine)

Sourced here only where a primary doc was read. Otherwise UNVERIFIED.

- Clear product page with SoftwareApplication-style facts (name, OS, category, offers), visible text matching markup. Rich result for SoftwareApplication: UNVERIFIED.
- Documentation pages with descriptive H1, stable URLs, canonical, sitemap lastmod.
- Fast, stable pages (CWV field data). Source: Google Search Central (see section 2).
- Brand and entity signals: consistent name "Open Books by Lumeo", Organization schema, same name on GitHub, npm, PyPI links. Principle is common SEO practice (UNVERIFIED as a ranking factor).
- Backlinks from developer communities (GitHub README, npm package pages, Hacker News, dev.to). Citation-worthy docs matter more for AI answers than classic rank (UNVERIFIED as a measured effect).

## 16. Automation checklist (CI and deploy)

Scriptable items, grouped by where they run.

Deploy (post-build, after production is live):
1. IndexNow ping: generate changed-URL list from sitemap diff (lastmod changed or new slugs), POST to `https://api.indexnow.org/indexnow` in batches of 10,000 or fewer. Key file served at `/<key>.txt`. Store the key as a secret, not in the repo. Log response code (200 or 202 accepted; 403 means key file not reachable).
2. Verify key file returns 200 and matches the key before POST.
3. Do not ping Google sitemap endpoint (retired). Do not call Indexing API for non-job pages.

Sitemap freshness (CI, on each build):
4. Generate sitemap.xml from route manifest; fail build if any indexable route is missing or any URL is non-absolute.
5. Check lastmod is ISO 8601 and changes only when content changes.
6. Check sitemap is under 50,000 URLs and 50MB; split with an index if needed.
7. Check every sitemap URL returns 200 and its canonical equals itself (no redirects, no noindex).

Robots validation (CI):
8. Fail if robots.txt disallows `/` for Googlebot or Bingbot in production.
9. Confirm `Sitemap:` line points to an absolute URL that returns 200.
10. Decide and encode policy for PerplexityBot, Perplexity-User, YouBot, bravebot-equivalent (Brave follows Googlebot rules, so no separate rule).

JSON-LD validation (CI):
11. Run schema validation (for example, schema-dts types at build, plus a headless check with the Schema Markup Validator API or a local validator) on each page with JSON-LD.
12. Assert JSON-LD text values appear in the rendered HTML (visible-text match rule).
13. Do not emit FAQPage or HowTo expecting rich results (see section 2).

Lighthouse and CWV budgets (CI):
14. Run Lighthouse CI on key templates (home, a docs page, a pricing or product page) on each PR.
15. Budgets to set (UNVERIFIED thresholds; use CrUX field data where available): LCP at or below 2.5s, INP at or below 200ms, CLS at or below 0.1, and a performance score floor you choose.
16. Fail PR on regression beyond agreed margin; alert, do not block, for first two weeks.

Canonical and hreflang (CI):
17. Assert every indexable page has one self-referencing canonical with absolute https URL.
18. Assert hreflang only where translated variants exist, and that each alternate lists itself and x-default.

Manual (not scriptable, do once per engine):
- Google Search Console and Bing Webmaster Tools domain verification (DNS TXT, one-time).
- Yandex and Naver and Seznam and Baidu verification: only if those markets are targeted.
- Brave Goggles creation: optional, manual web step.
- Re-check this document quarterly; Google structured data types change often.

## 17. Open questions (UNVERIFIED, need primary check)

- SoftwareApplication and BreadcrumbList rich result status in Google 2026.
- Which structured data types Google removed from Search Console in January 2026.
- Core Web Vitals thresholds as currently documented (web.dev).
- Bing to Copilot and ChatGPT grounding mechanism.
- Brave independent index and Web Search API details.
- Kagi submission process.
- Yahoo current backend.
- Perplexity-User robots.txt behavior (contested).
- Baidu sitemap submission eligibility.
- StatCounter worldwide shares for non-Google engines.
