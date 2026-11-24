# 05. MCP directories, skills and plugin distribution, monetisation, 90-day launch

Research date: 2026-11-24. Scope: how to list `@lumeo_hq/openbooks-mcp` and the harness kit. Builds on `01-distribution-formats.md` (client config formats, plugin layout, .mcpb fields) and `02-mcp-best-practices.md` (tool annotations, spec, registry overview). Those facts are not repeated here except where a newer source changes them.

Labels: **[V]** verified in a fetched primary source. **[S]** secondary source (blog, search snippet, third-party listing). **UNVERIFIED** not confirmed. Confidence: H / M / L.

## Ranked shortlist (read first)

1. **Publish to the official MCP Registry first.** Free, namespace-verified, and PulseMCP says it picks up registry entries once its submit form reopens. Verdict: **adopt**. Confidence H.
2. **Make the npm package pass registry checks**: `mcpName` in `package.json`, `io.github.<owner>/<name>` namespace, `server.json` with a `packages` entry. Verdict: **adopt**. Confidence H.
3. **Ship a Claude plugin bundle (skills + MCP config) in a public GitHub repo with a self-hosted `marketplace.json`.** Works today without any directory approval. Verdict: **adopt**. Confidence H.
4. **Anthropic directory: a plugin bundle is the only path for a local stdio server.** Remote-only connector submission needs an HTTPS endpoint, which would mean hosting customer financial documents. Verdict: **experiment** (bundle first; remote connector only after a privacy review). Confidence M.
5. **Do not rely on .mcpb for the directory.** Anthropic says local MCPB listings are deprecated. Verdict: **reject** for directory listing; keep .mcpb only as an optional manual install. Confidence H.
6. **Smithery and Glama: claim free listings** after step 1. Verdict: **experiment**. Confidence M (their docs were only partly readable).
7. **PulseMCP: wait.** Submissions are paused. Verdict: **reject for now**. Confidence H.
8. **Monetisation: keep the core permissively licensed; monetise hosting or verification as a separate service, but only after a data-handling review.** Verdict: **experiment** in month 3. Confidence M (evidence is anecdotal).

## 1. Listing an MCP server

### 1a. Official MCP Registry (registry.modelcontextprotocol.io)

Status: **preview**, "breaking changes or data resets may occur before general availability". [V] https://modelcontextprotocol.io/registry/quickstart (fetched 2026-11-24)

What it is: metadata only. It points to packages on npm, PyPI, Docker and others, or to a public remote URL. It does not host artifacts. It does not accept private servers. [V] https://modelcontextprotocol.io/registry/about.md

Steps (npm package, GitHub auth), per the quickstart [V]:
1. Add `"mcpName": "io.github.<github-owner>/<server-name>"` to `package.json`. Name must start with `io.github.<github-owner>/` for GitHub auth.
2. `npm publish --access public`. The registry does not host the package; npm must have it first.
3. Install `mcp-publisher` (GitHub release binary, or `brew install mcp-publisher`).
4. `mcp-publisher init` generates `server.json`. The `name` must match `mcpName`. Description limit is **100 characters**.
5. `mcp-publisher login github` (device-code flow at github.com/login/device).
6. `mcp-publisher publish`. Verify with `GET https://registry.modelcontextprotocol.io/v0.1/servers?search=<name>`.
- Other subcommands: `validate` (check without publishing), `status`. [V] same quickstart.
- Remote-only servers: publish a `remotes` array with no `packages`. The registry checks namespace ownership only, not that you control the remote URL. [V] same quickstart.
- Namespaces: GitHub (`io.github.*`) or DNS for a custom domain (`com.example/*`). [V] https://modelcontextprotocol.io/registry/authentication.md (linked from the quickstart; not separately fetched, M).
- Moderation: manual takedown; the registry delegates code scanning to npm, PyPI and others. [V] https://modelcontextprotocol.io/registry/about.md
- Review timeline: no SLA found. Publishing is immediate on success. UNVERIFIED whether listings are reviewed before they go live.
- Schema: `server.json` schema URL used in the quickstart is `https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`. [V] quickstart.
- Automation: GitHub Actions guide exists. [V] quickstart "Next Steps" (URL: https://modelcontextprotocol.io/registry/github-actions.md, not fetched).

What OpenBooks must prepare:
- `mcpName` set to the GitHub owner the project will publish under. Confirm which GitHub account owns the namespace before the first publish; the name cannot be changed casually.
- A `server.json` with a 100-character description, repository URL, version matching the npm version, and `environmentVariables` for any API key (`isSecret: true`).
- A README that states what the server does not verify (from `02` checklist item 20).

### 1b. Anthropic Connectors / plugin directory

Two submission kinds exist. [V] https://claude.com/docs/directory/publish.md (fetched 2026-11-24, page current as of that fetch):
- **Plugin bundle**: a plugin folder with skills, commands, agents, hooks and MCP references. Needs a **public GitHub repository** before the listing goes live.
- **MCP connector**: one **remote** MCP server, identified by an `https://` URL. Local servers are not accepted as connectors. [V] https://claude.com/docs/connectors/building/submission.md

Where to submit: developer portal https://claude.ai/directory/manage, then "Submit new", then "Plugin bundle" or "MCP connector". [V] both pages above.

Who can submit: any paid plan (Pro, Max, Ultra, Team, Enterprise). Free accounts cannot. On Team and Enterprise an Owner submits. [V] https://claude.com/docs/directory/publish.md

Connector requirements [V] https://claude.com/docs/connectors/building/submission.md and https://claude.com/docs/connectors/building/review-criteria.md:
- Every tool has a `title` and `readOnlyHint: true` (read tools) or `destructiveHint: true` (write tools). Missing titles or annotations are flagged in the portal.
- Tool names ≤ 64 characters.
- No catch-all "api_request" tool. Split read and write tools.
- Custom query tools name the target API in the description.
- Descriptions must not contain prompt-injection patterns (instructions to call other tools, to pull instructions from outside, or to promote products).
- Authentication: OAuth 2.0 for authenticated services. Public data needs none.
- Privacy policy: a URL is required in the listing. For local connectors, a "Privacy Policy" section in README and a `privacy_policies` array in `manifest.json` are also required. Missing policies cause immediate rejection.
- Listing fields: name ≤100, one-liner ≤200, description ≤2000, 1–5 categories, documentation URL, privacy URL, support contact, icon. The URL slug is permanent once published.
- Data handling disclosure: whether the API is first-party or proxied, and whether personal health data is handled.
- Testing: run every tool through MCP Inspector or as a custom connector in Claude, and confirm in "Test & launch".
- Seven policy acknowledgments in the "Compliance" step. [V] submission page.
- Unsupported: money transfer and AI image, video or audio generation. OpenBooks (verification, extraction) is not in these categories. [V] review-criteria page.
- Do not query Claude memory, chat history or user files; do not collect conversation data beyond the tool's need. [V] review-criteria page.

Review: every connector is scanned automatically and listed as **Community** by default. Anthropic may escalate to **Verified** review, which is manual and tests each tool. Plugin bundles: automated validation and security scan on every version, plus a person review for a new listing. [V] https://claude.com/docs/directory/publish.md and review-criteria page. Timeline: not fixed. UNVERIFIED for a number of days. Escalations: `mcp-review@anthropic.com`. [V] submission page.

Important for OpenBooks:
- The current package is a local stdio server (npm). A connector listing therefore needs a **remote HTTPS endpoint**. Hosting one means customer financial documents transit an external service. That conflicts with the project rule against sending customer documents to external services unless synthetic. Treat a connector listing as blocked until a privacy design exists.
- The plugin bundle route is open today. It can carry `.mcp.json` pointing at the npm package (`npx -y @lumeo_hq/openbooks-mcp`), so the local server runs on the user's machine.
- Anthropic says a plugin and its remote connector can be submitted together and paired, if the connector exists. [V] publish page.

### 1c. Smithery (smithery.ai)

- Publishing: a release is submitted by multipart form. Three release types: hosted JS module upload, external URL, and stdio MCPB bundle. A namespace (`namespace/server`) is required. [V] https://smithery.ai/docs/api-reference/servers/publish-a-server.md (search snippet, fetched content not confirmed; M)
- Pricing: UNVERIFIED. A third-party listing shows a free tier (25K RPCs/month, 3 namespaces). [S] https://www.everydev.ai/tools/smithery
- Hosted proxy: a secondary article says the run.tools and server.smithery.ai proxy was to shut down on 31 October 2026. UNVERIFIED; check before relying on hosted endpoints. [S] https://rywalker.com/research/smithery
- Requirements beyond namespace, review time: UNVERIFIED.

### 1d. Glama (glama.ai)

- Indexes open-source servers from GitHub. Submission: "Add MCP Server" with repo URL, display name and short description, behind GitHub OAuth. No submission API found. [S] Glama listing-guide blogs (search snippets, not Glama's own docs; L).
- Claim: DNS TXT at `_glama-claim.<domain>`, `/.well-known/glama.json`, or a `glama.json` file in the repo root listing GitHub maintainers. [S] same sources; L.
- Cost: listing free; boosted listing $49/month. [S] same sources; L. Verify on glama.ai before use.
- Recommended action: claim the listing by adding `glama.json` to the repo, then verify the copy.

### 1e. PulseMCP (pulsemcp.com)

- **Paused.** "We are not accepting new MCP server or client submissions right now, and we are not making changes to existing listings." Page updated 2026-09-03. Recommends publishing to the official registry; PulseMCP picks registry listings up automatically when submissions resume. [V] https://pulsemcp.com/submit (fetched 2026-11-24)

### 1f. mcp.so

- Not fetched. Submission process and requirements: UNVERIFIED. Treat as low priority until verified.

## 2. Skills, plugins, marketplaces, .mcpb

### 2a. Agent Skills (SKILL.md)

- Layout: `skill-name/SKILL.md` required; optional `scripts/`, `references/`, `assets/`. [V] https://agentskills.io/specification (fetched 2026-11-24)
- Frontmatter: `name` (≤64 chars, lowercase a-z, 0-9, hyphens; no leading, trailing or double hyphens; must match directory name); `description` (≤1024 chars). Optional: `license`, `compatibility` (≤500), `metadata` (string map), `allowed-tools` (experimental). [V] same
- Keep `SKILL.md` under 500 lines; move detail to `references/`. [V] same
- Validate: `skills-ref validate ./my-skill`. [V] same
- Progressive disclosure: name and description load at start; body on activation. [V] same
- The `01` doc's `skills-ref` note is confirmed.

### 2b. anthropics/skills (reference repo)

- Public repo of example skills (Apache-2.0 for many, including document skills docx, pdf, pptx, xlsx); `spec/` and `template/` directories. Install: `/plugin marketplace add anthropics/skills`, then `/plugin install document-skills@anthropic-agent-skills`. [V] https://github.com/anthropics/skills (WebFetch summary, M; per-skill license files not confirmed)
- Contribution process: not documented on the fetched page. UNVERIFIED. Do not assume a PR route into the repo.

### 2c. Claude Code plugins and marketplaces

Verified from https://code.claude.com/docs/en/plugin-marketplaces (fetched 2026-11-24):
- Marketplace = a git repo or directory with `.claude-plugin/marketplace.json`. Required top-level keys: `name`, `owner` (with `name`), `plugins` (each with `name` and `source`).
- Sources: relative path (`./plugins/x`), `github` (`repo`), `git-subdir` (`url`, `path`), `url`, `archive`, `npm`, `command`.
- Relative paths are from the marketplace root. `..` is rejected by `validate`.
- Entry `name` must equal the plugin's `plugin.json` name to avoid "Plugin not found" errors.
- Commands:
  - `claude plugin validate ./my-marketplace`
  - `claude plugin marketplace add <owner>/<repo>` (or a path)
  - `claude plugin install <plugin>@<marketplace>`
  - `claude plugin list`, `claude plugin details <name>`
- Reserved names: official Anthropic marketplace names are refused (e.g. `claude-plugins-official`). Per `01` doc, `claude-*` and `anthropic-*` are reserved; confirm the list at the marketplace-reference page (UNVERIFIED beyond the `01` note).
- Hosting: any git host, private repos allowed. Organisations can require a marketplace on every machine. [V] same page.
- The `01` doc's install-line uncertainty is now resolved: `claude plugin install name@marketplace` and `/plugin install name@marketplace` both verified [V].

### 2d. .mcpb (Claude Desktop extensions)

- Directory listing for local desktop extensions is **deprecated**. The directory "no longer accepts local MCP servers packaged as MCP Bundles (MCPB)". Include the server in a plugin instead. [V] https://claude.com/docs/connectors/building/submission.md and https://claude.com/docs/directory/publish.md
- Older support pages still describe a submission form for MCPB. Treat as stale. [S] search snippets, L.
- Manifest fields and CLI: as recorded in `01` doc [V]. `privacy_policies` array required for manifest_version 0.2+ for local connectors [V] submission page.

### 2e. Practical distribution plan

- One public repo `openbooks-harness` with `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `skills/openbooks-verify/SKILL.md`, `.mcp.json` pointing at the npm package, and a README with privacy section.
- Users install with `claude plugin marketplace add <owner>/openbooks-harness` then `claude plugin install openbooks@openbooks-harness`. Verified mechanism [V].
- Submit the same repo as a plugin bundle to the Anthropic directory once the privacy policy and docs URL exist. Expect Community listing [V].

## 3. Monetisation and licensing

Evidence base is weak. Most sources are practitioner blogs; several are self-promotional. Figures below are anecdotes, not market data. [S] for all items unless stated.

Patterns observed:
- **Free core plus paid hosted tier.** Example: a server with an MIT free tier and a $19/month cloud-hosted tier with unlimited queries. [S] https://dev.to/whoffagents/pricing-an-mcp-server-in-2026-why-we-charge-19mo-when-the-market-average-is-0-nig (L)
- **Local versus managed split.** Free open-source local version; proprietary managed cloud version. [S] Glama-hosted guide linked from https://dev.to/whoffagents/how-to-monetize-an-open-source-project-freemium-open-core-and-license-gating-4il6 (L)
- **Hosting and convenience pricing.** Customer pays for operations, not the tool. [S] https://dodopayments.com/blogs/mcp-server-pricing-models (L)
- **License gating.** Core tools free; premium tools checked against a subscription. [S] same DEV article (L)
- **Directory boost.** Glama boosted listing $49/month. [S] (L)
- **Hosted API examples from the `02` listings.** Invapi `@invapi/mcp-server` (npm, MIT per listing) requires a hosted API key for extraction. [S] https://socket.dev/npm/package/@invapi/mcp-server (L; licence per listing only)

Licensing implications for an open-source core:
- Permissive core (MIT or Apache-2.0) keeps directory listing, registry and marketplace distribution free of friction. Anthropic's own skills repo uses Apache-2.0 for many skills [V, M].
- AGPL is suggested by one guide to force commercial licences [S, L]. Consider the effect on adoption by enterprises before adopting; this is a legal question to confirm with counsel. UNVERIFIED.
- BSL (time-delayed, source-available, not OSI) is an option [S, L]. Not an OSI open-source licence.
- Directory terms: listings are subject to the Anthropic Software Directory Terms and Policy [V]. Not read in full. UNVERIFIED whether they restrict paid features in listed connectors.
- A hosted tier that processes customer documents triggers the operator's data rule. Any hosted tier needs synthetic-data testing and a privacy review first.

Verdict: keep the core permissive; monetise the hosted verification or support layer later. Confidence M.

## 4. Ranked 90-day launch checklist

Assumes the repo's current licence and the GitHub owner for namespace are confirmed first (not checked in this research; check `LICENSE` before day 1).

| # | Days | Action | Verdict | Dependency |
|---|---|---|---|---|
| 1 | 1–7 | Confirm licence file and GitHub namespace owner. Decide `io.github.<owner>/openbooks` | adopt | none |
| 2 | 1–10 | Add `mcpName`, verify npm publish, write `server.json` (desc ≤100 chars), publish via `mcp-publisher` | adopt | 1 |
| 3 | 1–14 | Fix tool annotations: `title`, `readOnlyHint` / `destructiveHint`, names ≤64, no catch-all tools | adopt | none |
| 4 | 7–21 | Write privacy policy, docs page, support contact; add privacy section to README | adopt | none |
| 5 | 14–28 | Build plugin bundle (`.claude-plugin`, SKILL.md validated with `skills-ref`, `.mcp.json`); pass `claude plugin validate` | adopt | 3 |
| 6 | 21–35 | Publish public GitHub repo as a self-hosted marketplace; test install on a clean machine | adopt | 5 |
| 7 | 28–42 | Submit plugin bundle to Anthropic directory (portal, paid account) | experiment | 4, 5, 6 |
| 8 | 35–49 | Claim Glama listing (`glama.json` in repo); check Smithery namespace and pricing | experiment | 2 |
| 9 | 42–56 | Run MCP Inspector and a labelled eval set (from `02` item 18) and publish results | adopt | 3 |
| 10 | 56–70 | Decide remote endpoint for connector listing only after privacy design; synthetic-data test | experiment | 9 |
| 11 | 70–90 | Pilot paid hosted tier or support plan with synthetic docs only; measure installs and conversion | experiment | 10 |
| X | any | Resubmit to PulseMCP when its form reopens | reject for now | PulseMCP status |
| X | any | Publish .mcpb for directory listing | reject | Anthropic deprecation |

Success signals by day 90 (proposed, not benchmarked): registry entry live; plugin installable from marketplace on a clean machine; at least one directory listing status recorded; zero customer documents sent to any external service during testing.

## Open items (UNVERIFIED)

- Anthropic directory review duration (days). Not published.
- Registry GA date and any review step before listing goes live.
- mcp.so submission process.
- Smithery pricing and whether the hosted proxy was shut down.
- Glama claim methods on glama.ai's own docs (only blogs read).
- Anthropic directory policy text (not read).
- Per-skill licences in anthropics/skills.
- Reserved marketplace name list.
- Whether the npm package `@lumeo_hq/openbooks-mcp` currently exists at the stated version (not checked; it is the user's package).

## Sources

- https://modelcontextprotocol.io/registry/quickstart
- https://modelcontextprotocol.io/registry/about.md
- https://claude.com/docs/connectors/building/submission.md
- https://claude.com/docs/connectors/building/review-criteria.md
- https://claude.com/docs/directory/publish.md
- https://pulsemcp.com/submit
- https://agentskills.io/specification
- https://github.com/anthropics/skills
- https://code.claude.com/docs/en/plugin-marketplaces
- https://smithery.ai/docs/api-reference/servers/publish-a-server.md (via search)
- https://www.everydev.ai/tools/smithery (S)
- https://rywalker.com/research/smithery (S)
- https://dev.to/whoffagents/pricing-an-mcp-server-in-2026-why-we-charge-19mo-when-the-market-average-is-0-nig (S)
- https://dev.to/whoffagents/how-to-monetize-an-open-source-project-freemium-open-core-and-license-gating-4il6 (S)
- https://dodopayments.com/blogs/mcp-server-pricing-models (S)
- https://socket.dev/npm/package/@invapi/mcp-server (S)
- Glama listing guides via search: https://dev.to/kfuras/glama-clones-your-repo-smithery-proxies-your-http-mcpso-wants-a-markdown-line-18f5 (S)
