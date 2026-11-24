# 30-day launch checklist (Open Books)

Source: docs/seo/research/04-dev-discovery-channels.md, section 4. Every item is an owner step unless marked agent. Nothing is posted by the agent. Items marked UNVERIFIED depend on rules that were not fetched.

## Days 1-3: metadata (cheap, unblocks the rest)

- [ ] 1. Fill npm `keywords`, `description`, `repository`, `homepage` in the four `@lumeo_hq/openbooks-*` packages and the root CLI package; confirm README renders on npm. (agent-ready, owner publishes)
- [ ] 2. Check that `@lumeo_hq/openbooks` package.json has `mcpName` set to `io.github.Sagexd08/openbooks-mcp`, the license matches the README (Apache-2.0), and the version is 0.2.3. The Python `openbooks-mcp` package is retired; do not republish it.
- [ ] 3. Add GitHub topics and a social preview image to Sagexd08/OpenBooks (manual upload).
- [ ] 4. Publish `@lumeo_hq/openbooks` 0.2.3 to npm from packages/js/mcp. See mcp-registry.md.

## Days 4-7: MCP registry

- [ ] 5. Run `mcp-publisher validate` in packages/js/mcp, then `login github` and `publish`. See mcp-registry.md.
- [ ] 6. Confirm the listing with the registry search URL in mcp-registry.md.

## Days 8-14: directories

- [ ] 7. Submit to Glama (Add Server, claim listing); add the Glama badge to the README. Glama `glama.json` format UNVERIFIED.
- [ ] 8. Submit to Smithery, PulseMCP and mcp.so. Confirm each form on its site first (UNVERIFIED).
- [ ] 9. Open the awesome-mcp-servers PR using awesome-mcp-servers-pr.md. Include the Glama backlink in the PR description.

## Days 15-21: content

- [ ] 10. Publish one dev.to article using devto-article-outline.md, canonical link to https://openbooks.lumeo.co.in/docs. Run every code block first.
- [ ] 11. Answer 3-5 relevant Stack Overflow or Reddit questions honestly, disclosing affiliation. Read each forum's rules first (UNVERIFIED).

## Days 22-30: launch

- [ ] 12. Show HN using show-hn.md, only if the install path works on a clean machine with no signup. Stay in the thread for the whole day.
- [ ] 13. Product Hunt: read current guidelines first (UNVERIFIED). Skip if they cannot be read.
- [ ] 14. India communities (FOSS United, Tally/GST developer groups): join, contribute, then share, following each group's rules. Use community-posts.md as a starting point.
- [ ] 15. Reddit posts from community-posts.md: check each subreddit's rules and flair first (UNVERIFIED).

## Measure (weekly)

- [ ] npm weekly downloads for `@lumeo_hq/openbooks`
- [ ] npm weekly downloads for `@lumeo_hq/openbooks`
- [ ] Registry search hits for `io.github.Sagexd08/openbooks-mcp`
- [ ] Referrals from GitHub, dev.to and HN to https://openbooks.lumeo.co.in/docs (analytics tool of the owner's choice)

## Blockers to clear before any post

- [ ] Licence statement consistent across packages.
- [ ] Sample CSV path in the repo confirmed for the demo commands.
- [ ] Retention and storage statement for the hosted workspace, taken from the live docs (not from this file).
