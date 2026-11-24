# Token efficiency for an MCP server and skills kit (document verification)

Research date: 2026-11-24. Scope: fewest LLM tokens per verification task, measured honestly. No code changes. Labels: VERIFIED (fetched primary source), VENDOR (vendor claim), INDEPENDENT (third-party measurement), HYPOTHESIS (ours, to test), UNVERIFIED (could not confirm). Confidence: H/M/L.

## Ranked shortlist

1. **Verdict-first response tiers (verdict / summary / rows).** HYPOTHESIS. Expected saving: largest, because output rows dominate tool results. Cost: low. Accuracy risk: low if the verdict is derived from the same checks. Verdict: adopt, measure first.
2. **File handle plus proof hash instead of inlined rows.** HYPOTHESIS built on VENDOR evidence (see 3). Cost: low to medium. Verdict: adopt.
3. **Typed refusal codes instead of prose.** HYPOTHESIS. Saves output and retry tokens; stable enums also make scoring deterministic. Cost: low. Verdict: adopt.
4. **Keep the tool catalog small (under 10 tools) rather than adding tool search.** VERIFIED: Anthropic recommends standard tool calling below 10 tools or under 100 tokens of definitions, and tool search above 10 tools or 10k tokens of definitions ([Tool search tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool), fetched 2026-11-24). Expected: avoids a search round-trip. Verdict: adopt the small catalog; reject tool search for now, revisit if the kit grows past 10 tools.
5. **Stable short field names and compact serialization.** HYPOTHESIS. Evidence is weak: one informal single-file test showed Markdown 11,612 tokens vs JSON 13,869 ([OpenAI community post](https://community.openai.com/t/markdown-is-15-more-token-efficient-than-json/841742), INDEPENDENT, low confidence). A separate 11-dataset study reported TOON at 2,744 tokens with 73.9% accuracy, and Markdown-KV at 2.5 to 2.8 times JSON ([Medium, SoftServe](https://medium.com/softserve-technical-communication/rethinking-llm-inputs-json-against-toon-and-markdown-kv-b713bcbe7eb5), INDEPENDENT, low confidence). Verdict: experiment on our own corpus.
6. **Sample-on-demand and pagination.** HYPOTHESIS. Return counts and a fixed-size sample; fetch more by cursor. Cost: low. Accuracy risk: a sample can hide a failing row, so the verdict must never rely on the sample. Verdict: adopt with that rule.
7. **Caching by content hash.** HYPOTHESIS. Saves parse compute and repeat tool calls; saves tokens only when a repeat call would otherwise re-inline data. Cost: medium (cache invalidation on parser version). Verdict: adopt for compute; do not count it as a token win.
8. **Code execution with MCP (verify in a sandbox, return only the diff).** VENDOR: 150,000 tokens down to 2,000 on one workflow, 98.7%, published 2025-11-04 ([Anthropic engineering post](https://www.anthropic.com/engineering/code-execution-with-mcp), fetched 2026-11-24). Single example, not a general benchmark. Cost: high (sandbox, security review). Verdict: experiment later for batch jobs only.

## 1. Tool-definition bloat and loading

- VERIFIED: a multi-server setup (GitHub, Slack, Sentry, Grafana, Splunk) can consume about 55k tokens of definitions before work starts; tool search "typically" cuts this by over 85% ([Tool search docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)).
- VERIFIED: deferred tools still must be sent in the request; `defer_loading` controls only what enters context. Tool search usage is not metered as a separate tool, and loaded definitions count as input tokens (same source).
- VERIFIED: most clients load all tool definitions up front; Anthropic's post describes exploring a filesystem of tool modules instead ([code-execution post](https://www.anthropic.com/engineering/code-execution-with-mcp)).
- VENDOR: the same docs cite 134K tokens of definitions before optimization in an internal setting (secondary quote; not re-verified).
- INDEPENDENT, low confidence: GitHub MCP definitions reported at 42k to 55k tokens across 93 tools, and 14,406 tokens across 86 tools using o200k_base ([WorkOS](https://workos.com/blog/mcp-server-token-cost), [Unblocked](https://getunblocked.com/blog/github-mcp-token-cost/), [PolicyLayer](https://policylayer.com/token-cost/github)). Counts vary by toolset and tokenizer; cite only as ranges.
- UNVERIFIED: the "context jumped from 34k to 80k" anecdote; not used.

## 2. Progressive disclosure for skills

- VENDOR: skills expose only name and description from frontmatter at runtime; full instructions load when triggered ([Anthropic, Equipping agents with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills), published 2025-10-16; metadata detail from [claude.com blog](https://claude.com/blog/building-agents-with-skills-equipping-agents-for-specialized-work), not fetched).
- Implication (HYPOTHESIS): keep SKILL.md short; move parser tables and checklists into referenced files read on demand.

## 3. Response shaping and parser output inflation

- Response shaping: VENDOR (Anthropic code-execution post) says intermediate results pass through the model, adding about 50,000 tokens for a 2-hour transcript example. This supports returning handles, not payloads.
- Markdown vs DocLang (Docling serializers, one PDF): Markdown 6,348 tokens; DocLang 16,232, or 9,288 with location tags stripped. Bounding-box tags also lowered one structure-question accuracy from 75% to 62.5% ([Towards AI](https://pub.towardsai.net/i-tried-to-prove-doclang-beats-markdown-for-pdf-llm-the-data-said-otherwise-19d256cbaa00), INDEPENDENT, single document, low confidence). Lesson: strip coordinates from default output.
- Docling, Marker, LlamaParse: no published token counts found. UNVERIFIED. Do not quote numbers until we measure them.
- Financial tables: merged cells and formulas inflate Markdown tables; expected to favor cell-level records with stable IDs (HYPOTHESIS).

## 4. Measurement methodology (required for an honest claim)

1. Corpus: synthetic or approved documents only, with fixed seeds and a published manifest.
2. Tokenizer: state it per count. Use the model's own counting where available (UNVERIFIED: exact endpoint behavior; check current API docs), and report tiktoken o200k_base as a proxy only, labelled.
3. Models: pin IDs (e.g. claude-haiku-5-5) and record the date.
4. Count separately: tool definitions per turn, tool arguments, tool results, assistant output, and cache reads/writes. Report input and output.
5. Baseline and treatment run on the same documents, same task prompts, same turn budget, N repeats, with mean and variance.
6. Accuracy gate: report verdict correctness against the labelled answer set. A token saving that drops accuracy does not count.
7. Include failure paths (refusals, timeouts, retries) in totals.
8. Publish raw transcripts, token logs, scripts, and the failing cases. Extend the existing `harness/bench/token_cost.py` (not reviewed here) rather than building a new harness.

## Open items

- Fetch Docling, Marker, and LlamaParse documentation for output formats and any published token data.
- Confirm current tool-search GA status and beta headers before relying on them.
