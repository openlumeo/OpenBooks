# 07 Launch Playbook: Open Books (dev tool, MCP server, agent skills kit)

Research date: 2026-11-24. Labels: **[VERIFIED]** = fetched or quoted from a primary page; **[SECONDARY]** = third-party tracker or press; **[VENDOR]** = company self-report; **[UNVERIFIED]** = no source found, or conflicting numbers. Confidence: H/M/L.

## 1. Summary

A small team cannot out-spend incumbents on ads, so it wins on (a) a narrow, checkable claim, (b) a runnable demo in under 60 seconds, (c) a reproducible benchmark, and (d) distribution where developers already look (GitHub, MCP directories, Show HN). Star counts in this space came mostly from trending/HN spikes and from being installable inside existing agent tools, not from paid campaigns. Star numbers below are mostly self-reported or third-party and should be treated as directional.

## 2. Evidence from comparable launches

| Project | What is confirmed | Source | Label / conf. |
|---|---|---|---|
| Docling (IBM, MIT) | Open-sourced July 2024; IBM says >8,000 GitHub stars within the first months; a later Docling paper reports 10k stars in under a month and #1 GitHub trending worldwide in Nov 2024 | [IBM Research blog](https://research.ibm.com/blog/docling-generative-AI), [Docling technical report](https://arxiv.org/html/2501.17887v1) | VENDOR / M. Show HN thread not located. |
| Firecrawl | YC launch post: "gained 8000 stars on GitHub" within about three months of an April launch; channels listed are YC listing, GitHub star requests, website, direct email. Series A post cites 48k stars (Aug 2025). Changelog dated 2026-11-09 marks 200K stars. | [YC launch page](https://www.ycombinator.com/launches/LTf-firecrawl-open-source-crawling-and-scraping-for-ai-ready-web-data), [200K changelog](https://www.firecrawl.dev/changelog/200k-github-stars.md), [Series A post](https://www.firecrawl.dev/blog/firecrawl-v2-series-a-announcement.md) | VERIFIED for the fetched pages; 48k figure from search snippet only. Confidence M. Trendshift says first #1 on GitHub Trending on 2024-05-22 [SECONDARY](https://trendshift.io/repositories/14644). |
| Browser Use | Show HN item 42052432 (exists per search results; points not captured). Launch HN for cloud product: 234 points. TechCrunch (Mar 2025): viral after a post about Manus using it drew >2.4M views on X. YC page: 40k stars in 3 months. | [Show HN item](https://news.ycombinator.com/item?id=42052432), [Launch HN](https://hn.svelte.dev/item/43173378), [TechCrunch](https://techcrunch.com/2025/03/12/browser-use-one-of-the-tools-powering-manus-is-also-going-viral), [YC page](https://ycombinator.com/companies/browser-use) | Mixed VERIFIED/SECONDARY. Conf. M on the event, L on exact star numbers (figures differ across pages: 35k, 40k, 79k). |
| Skyvern | Post titled "We open-sourced and ended up #1 on Hackernews" | [Skyvern blog](https://www.skyvern.com/blog/we-open-sourced-and-ended-up-1-on-hackernews/) | VENDOR; body not fetched. Use as a case study to read, UNVERIFIED on numbers. |
| Context7 (Upstash, MIT) | Repo created March 2025. Third-party directories show about 57k to 65k stars in mid/late 2026. Launch channels and Product Hunt listing: not found. | [GitHub repo](https://github.com/upstash/context7), [OSS Insight](https://ossinsight.io/analyze/upstash/context7) | SECONDARY; launch channels UNVERIFIED. Conf. L on channels. |
| Marker (Datalab) | Release notes describe selective OCR: text layer first, VLM only for scanned pages, equations, low-confidence tables. Headline olmOCR-bench balanced score 76.0 (digital-only 83.5). A secondary write-up cites MinerU 72.7 and Docling 50.3 on the same bench. Throughput conflicts: 2.9 pages/s in the release table vs 23.7 pages/s in the write-up. | [Marker releases](https://github.com/datalab-to/marker/releases), [Marker repo](https://github.com/VikParuchuri/marker) | VENDOR for the 76.0 figure; SECONDARY for MinerU/Docling comparison; throughput conflict is UNRESOLVED. |
| Show HN norms | Title must start "Show HN:"; work must be something people can try; the thread is for feedback. | [Show HN guidelines](https://news.ycombinator.com/showhn.html), [HN guidelines](https://news.ycombinator.com/newsguidelines.html) | VERIFIED (snippet-level). Conf. H. |

Star-growth read-across: the best-documented curve is Firecrawl (about 8k in 3 months, then 48k by Aug 2025 and 200k by Nov 2026). These are company-reported. No verified curve exists for Open Books; do not promise any number.

## 3. Channels: what the evidence supports

- **GitHub trending and README:** Docling and Firecrawl both document trending placements [VERIFIED for Docling/IBM blog, Trendshift for Firecrawl]. Conf. M. Driven by a fast install-to-first-result path.
- **Show HN:** Browser Use and Skyvern both report HN-driven traction [VERIFIED for existence of threads; numbers SECONDARY]. Conf. M. Works best with a runnable link and an honest limitation list.
- **Launch HN / YC listing:** Firecrawl and Browser Use used YC listings [VERIFIED]. Only relevant if the team is in YC; otherwise N/A.
- **X and viral posts:** Browser Use's March 2025 spike came from a third-party demo post [SECONDARY]. Conf. M. Not reproducible on demand; treat as upside.
- **MCP directories:** Context7's distribution through MCP registries is plausible but its launch sequence is UNVERIFIED. Conf. L.
- **Product Hunt:** No verified effect found for the comparable projects. UNVERIFIED. Low priority.
- **Reddit, newsletters, YouTube:** Not researched in depth; UNVERIFIED for this set.

## 4. Benchmark-led credibility: what works and what backfires

Works:
- Publish the harness, scorer and raw outputs in the repo, so anyone can rerun (Marker points to its benchmark harness [VENDOR]; Unstructured open-sourced its evaluation method [VENDOR, per search snippet]).
- Name the exact metric and dataset (for example olmOCR-bench, balanced mode) and state the hardware (Marker cites B200).

Backfires or invites attack:
- Benchmark validity disputes are documented. LlamaIndex argues olmOCR-bench is not diverse enough and that its exact-match unit tests penalize correct output [VERIFIED snippet, [LlamaIndex review](https://www.llamaindex.ai/blog/olmocr-bench-review-insights-and-pitfalls-on-an-ocr-benchmark)]. Datalab's founder argues scoring flaws can penalize correct OCR [SECONDARY]. Lesson: a self-built benchmark gets the same scrutiny; publish the scorer and failure examples.
- A December 2025 arXiv paper states no public PDF parser converts documents without errors, especially for math [VERIFIED, [arXiv 2512.09874](https://arxiv.org/html/2512.09874v1)]. Lesson: claim wins on a named slice, not "best overall".
- Specific backfire cases (a launch collapsing after unreproducible numbers) were NOT found. UNVERIFIED as a pattern; treat the risk as inferred, conf. M.

## 5. Recommendations for Open Books

Ranked shortlist (launch-side only; no architecture change proposed):

1. **Reproducible finance-statement benchmark page** using synthetic or approved documents only. Adopt. Expected benefit: credibility. Cost: low. Accuracy risk: a narrow dataset invites "cherry-picked" critique; mitigate by publishing failures.
2. **One-command demo** (`npx`/`uvx` or MCP install line) with a 60-second GIF. Adopt. Cost: low.
3. **MCP directory submissions and skills pack listing.** Adopt after the server is stable. Cost: low.
4. **Show HN with a "what it does not do" section.** Experiment, timed after the benchmark page is live.
5. **Product Hunt launch.** Reject for v1; no comparable evidence of value found.

Per-recommendation fields (hypothesis / evidence / performance benefit / complexity / memory / cost / accuracy risk / benchmark / verdict):

- **Benchmark page.** Hypothesis: a public, rerunnable bench earns trust with technical buyers. Evidence: Section 4 [VERIFIED/SECONDARY]. Benefit: conversion from README to trial. Complexity: low (the harness already exists in `harness/bench`). Memory: none. Cost: near zero. Accuracy risk: medium (metric disputes). Benchmark: rerun from a clean clone on a fixed hardware note. Verdict: **adopt**.
- **Demo GIF and one-command install.** Hypothesis: time-to-first-result drives stars. Evidence: Docling/Firecrawl install-first pattern [SECONDARY]. Complexity: low. Verdict: **adopt**.
- **Comparison page against named competitors.** Hypothesis: buyers search "X vs Y". Evidence: none verified for comparable launches. Accuracy risk: high (competitor numbers must be reproduced, not copied). Verdict: **experiment**, only with reproduced numbers and dated versions.
- **Show HN.** Hypothesis: a single HN spike gives a star burst but low retention. Evidence: Browser Use, Skyvern [SECONDARY]. Verdict: **experiment**, one attempt.
- **Hype-based X threads or paid ads.** Verdict: **reject** (no evidence of benefit for dev tools in this set).

## 6. 30/60/90-day plan

**Days 1 to 30 (make it installable and checkable)**
- Fix the README: one-line install, a 60-second demo, a limitations section, and a link to the bench.
- Publish the synthetic-document benchmark with scorer, raw outputs and hardware note.
- Record the demo GIF (one per workflow: statement to CSV, MCP call from an agent client).
- Submit to MCP directories once the server passes a clean-machine install test.
- Seed 5 to 10 technical users for feedback. Do not buy stars.

**Days 31 to 60 (distribution)**
- Publish a benchmark write-up on the docs site, with failure cases.
- Show HN, one attempt, on a weekday morning US time, with the bench link in the first comment and a list of what does not work yet.
- Publish the skills kit as a versioned pack with install instructions for each agent client.
- Respond to every issue within 48 hours during launch week.

**Days 61 to 90 (retain and compare)**
- Publish a reproducible comparison page only where numbers are rerun by the team; date and version every competitor row.
- Write one case study with an anonymized or synthetic statement.
- Decide on Product Hunt or newsletters based on Show HN data (stars per day, install counts, issue volume).

## 7. Launch-day checklist

- [ ] Clean-machine install test passes (MCP and CLI)
- [ ] README links to bench, demo GIF, limitations, license
- [ ] Bench reruns from a fresh clone; results match the page
- [ ] No customer documents anywhere in the demo or bench (synthetic or approved only)
- [ ] Show HN title starts "Show HN:" and names what it does; no superlatives
- [ ] First HN comment: what it is, how it was tested, known failures
- [ ] Issue templates and a support response owner for launch day
- [ ] Analytics: installs, stars per hour, issues opened (no personal data)
- [ ] MCP directory listings live and linked back to the repo

## 8. Assets to prepare

1. Demo GIF (under 15 s) and a 60 s video
2. Benchmark page with scorer, raw outputs, hardware, dataset description
3. Comparison page (only reproduced numbers, versioned)
4. Docs: quickstart, MCP tool reference, skills kit install, FAQ on limits
5. Architecture diagram (one figure)
6. Launch post and Show HN first-comment draft
7. MCP registry metadata (description, tools list, example prompts)

## 9. Top 5 mistakes to avoid

1. **Unreproducible or cherry-picked benchmark numbers.** Publish the harness, the scorer, and failures.
2. **Claiming "best overall".** Name the slice (for example, digital-PDF statements) and say what fails.
3. **Buying or faking stars.** Not evidenced as helpful; reputational risk high [UNVERIFIED as a pattern, conf. M].
4. **Launching before install works on a clean machine.** The first 100 users decide the rest.
5. **Sending real customer documents to outside services for demos or benchmarks.** Use synthetic or approved documents only.

## 10. Open gaps

- No verified Show HN point counts for Docling, Firecrawl, Context7 or Marker.
- Marker throughput conflict (2.9 vs 23.7 pages/s) unresolved.
- Context7 launch channel sequence not found.
- No verified case of a launch failing due to unreproducible claims.
