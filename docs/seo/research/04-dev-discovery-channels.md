# 04 - Developer discovery channels (Open Books)

Scope: npm `@lumeo_hq/openbooks` (+ -core, -statements, -gateways, -doctor), PyPI `openbooks` 0.2.0 and npm `@lumeo_hq/openbooks-mcp`, GitHub Sagexd08/OpenBooks. Status: research as of 2026-11-23. Items marked UNVERIFIED could not be confirmed from a fetched source.

Fetch notes: MCP Registry docs, Show HN rules, npm keyword docs, PyPI core metadata and awesome-mcp-servers were fetched. Smithery yaml docs (404), awesome-mcp CONTRIBUTING (no PR template found), Glama (no submission doc found), npm ranking page (404), Reddit (blocked), Product Hunt (redirect not followed) could not be verified.

## 1. Package registries

| Channel | How to list / what it rewards | Source | Review time | Effort |
|---|---|---|---|---|
| npm search | `keywords` (array) and `description` both "help people discover your package as it's listed in npm search". README-ranking claim UNVERIFIED. Download/quality ranking: UNVERIFIED (npm ranking page 404). | https://docs.npmjs.com/cli/v10/configuring-npm/package-json#keywords | none | S: 30 min (fill keywords, description, repository, homepage) |
| npms.io / Snyk Advisor | Scores derived from package metadata, maintenance and popularity; no submission. Exact weights UNVERIFIED. | UNVERIFIED | none | S |
| PyPI search | `keywords` ("assist searching... in a larger catalog"), `classifiers` (dynamic PyPI list), `Project-URL` ("URL and label, separated by a comma"). Whether classifiers affect search ranking: not stated in spec. | https://packaging.python.org/en/latest/specifications/core-metadata/ | none | S |
| GitHub topics + social preview | Repo topics and social preview image (manual upload). Topic/search ranking rules UNVERIFIED. | UNVERIFIED | none | S: 1 h |

## 2. MCP discovery

### 2a. Official MCP Registry (registry.modelcontextprotocol.io)
- Publish via `mcp-publisher` CLI: `init`, `login github`, `publish`, `validate`.
- Hosts metadata only; the package must already exist on its registry (npm/PyPI).
- Namespace: GitHub auth requires `name` starting with `io.github.<github-user>/`. The GitHub user here is `Sagexd08`, so the name is `io.github.Sagexd08/openbooks-mcp`. DNS auth allows a custom domain prefix.
- Ownership marker: npm uses `mcpName` in package.json; PyPI uses an `mcp-name: <server-name>` line (or HTML comment) in the package README. The name must match server.json.
- Description max 100 characters.
- Source: https://modelcontextprotocol.io/registry/quickstart (registry is in preview).

**Required README line (npm package `@lumeo_hq/openbooks-mcp`):**
```
mcp-name: io.github.Sagexd08/openbooks-mcp
```
Must ship in the PyPI release that the registry checks, so republish 0.1.x or bump to 0.1.1.

**server.json template (PyPI package; schema per registry docs, verify with `mcp-publisher validate`):**
```json
{
  "$schema": "https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json",
  "name": "io.github.Sagexd08/openbooks-mcp",
  "description": "Search and execute Open Books financial-statement tools over MCP.",
  "repository": { "url": "https://github.com/Sagexd08/OpenBooks", "source": "github" },
  "version": "0.1.0",
  "packages": [
    {
      "registryType": "pypi",
      "identifier": "openbooks-mcp",
      "version": "0.1.0",
      "transport": { "type": "stdio" }
    }
  ]
}
```
Note: the registry's npm example includes `environmentVariables`; add any required env vars for openbooks-mcp (UNVERIFIED which ones apply). Remote-only variant uses a `remotes` array instead of `packages`.

Effort: M (about 2 h including republish). Review time: UNVERIFIED.

### 2b. Smithery
- Config file `smithery.yaml` in repo root. Format doc returned 404; template UNVERIFIED. Submission flow UNVERIFIED.
- Effort: S-M. Review time: UNVERIFIED.

### 2c. Glama
- Directory of MCP servers with "Add Server" and "Claimed" status. Glama `glama.json` format and claim steps: UNVERIFIED (no doc fetched).
- Glama is also a backlink target for awesome-mcp-servers (see 2e).
- Effort: S. Review time: UNVERIFIED.

### 2d. PulseMCP, mcp.so, Cursor/Claude directories
- Listing method, file formats and review times: UNVERIFIED (not fetched). Treat as "submit form + repo URL" until checked.

### 2e. awesome-mcp-servers PR (punkpeye/awesome-mcp-servers)
- Verified: one server per line, server name linked to repo, short description, placed in a category, alphabetical order within category, public GitHub repo required (remote-only goes to awesome-remote-mcp-servers), PR description should note the Glama backlink (badge in README or site link) - they "prioritize" PRs that include it.
- Exact line template: UNVERIFIED (CONTRIBUTING.md not retrieved). Use the existing line format of neighbouring entries.
- Effort: S (30 min). Review: UNVERIFIED.
- Source: https://github.com/punkpeye/awesome-mcp-servers

### 2f. context7 library listing
- Listing process and required format: UNVERIFIED.

## 3. Community / launch channels

| Channel | Verified rule | Source | Effort |
|---|---|---|---|
| Hacker News Show HN | Must be something people can "run on their computers or hold in their hands"; creator must be around to discuss; make it easy to try without signup/email. Not allowed: blog posts, sign-up pages, newsletters, lists, landing pages, quickly-generated one-offs, unready work; no asking friends to upvote. Version releases generally not substantive. Free/OSS requirement: not stated. | https://news.ycombinator.com/showhn.html | M (post + live demo, stay in thread) |
| Reddit r/mcp, r/LocalLLaMA, r/fintech, r/IndiaInvestments, r/Accounting | Rules not fetched (blocked). Assume self-promo limits and flair rules: UNVERIFIED. Check each sub's sidebar before posting. | blocked | S per post |
| dev.to / Hashnode | Publishing is open; tag and canonical-link rules UNVERIFIED. | UNVERIFIED | M (article) |
| Product Hunt | Guidelines redirected to help.producthunt.com; content not retrieved. | UNVERIFIED | L (launch day prep) |
| Stack Overflow | Answers must be genuinely helpful; self-promo disclosure rules UNVERIFIED. Answer real questions about tax/statement parsing only where relevant. | UNVERIFIED | S per answer |
| Indie Hackers, newsletters (e.g. TLDR), awesome lists (other than MCP) | Submission rules UNVERIFIED. | UNVERIFIED | S-M each |
| India: FOSS United, Tally/GST developer groups (WhatsApp/Telegram/Discord) | Membership and promo rules UNVERIFIED. Join, contribute, then share. | UNVERIFIED | S |

## 4. Prioritized 30-day launch checklist

Day 1-3 (metadata, cheap, unblocks everything)
1. Fill npm `keywords`, `description`, `repository`, `homepage` in all four `@lumeo_hq/openbooks-*` packages; confirm `README` renders.
2. Add PyPI `Project-URL` and `keywords`/`classifiers` to `openbooks`.
3. Add GitHub topics and social preview image to Sagexd08/OpenBooks.
4. Set `mcpName` in the npm package.json and publish.

Day 4-7 (MCP registry)
5. Write server.json (template above); run `mcp-publisher validate`, then `login github` and `publish`.
6. Confirm via `curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.Sagexd08/openbooks-mcp"`.

Day 8-14 (directories)
7. Submit to Glama (Add Server, claim listing); add Glama badge to README.
8. Submit to Smithery, PulseMCP, mcp.so; confirm each submission format on its site before filling in (UNVERIFIED).
9. Open awesome-mcp-servers PR: one line, alphabetical in its category, note Glama backlink in PR description.

Day 15-21 (content)
10. Publish one dev.to / Hashnode tutorial with canonical link to docs at https://openbooks.lumeo.co.in/docs.
11. Answer 3-5 relevant Stack Overflow / Reddit questions honestly, disclosing affiliation.

Day 22-30 (launch)
12. Show HN with a try-without-signup demo (only if the demo runs in-browser or CLI with no signup); be present for comments.
13. Product Hunt launch only after reading current guidelines (UNVERIFIED).
14. India communities (FOSS United, Tally/GST groups): share after joining; follow group rules.

Measure: npm weekly downloads, PyPI downloads, registry search hits, referral from docs site.
