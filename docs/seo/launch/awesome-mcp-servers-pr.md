# awesome-mcp-servers PR (draft, not opened)

Target: https://github.com/punkpeye/awesome-mcp-servers

Research status (docs/seo/research/04-dev-discovery-channels.md, 2e): one server per line, name linked to the repo, short description, placed in a category, alphabetical within the category, public GitHub repo required. The exact line template and category names are UNVERIFIED because CONTRIBUTING.md was not retrieved. Copy the format of the neighbouring entries in the file you are editing before opening the PR.

## The line (one line, placement UNVERIFIED)

Place it in the finance or documents category, alphabetically among its neighbours by the server name. Check the category name in the live file first.

```markdown
- [Sagexd08/OpenBooks](https://github.com/Sagexd08/OpenBooks) - Verify bank statements, settlements and tax documents: one proven JSON per file, or a typed refusal that names the reason. npm package `@lumeo_hq/openbooks`, run with `npx -y -p @lumeo_hq/openbooks openbooks-mcp`.
```

Remove the emoji or marker suffixes unless the neighbouring lines use them. If they do, add the same markers that the file's own legend defines (UNVERIFIED which ones apply).

## PR title

```
Add Open Books MCP server (openbooks-mcp)
```

## PR description

```markdown
Adds Open Books, an MCP server that lets an agent verify bank statements, payment settlements and tax documents.

- Repository: https://github.com/Sagexd08/OpenBooks (public, npm package `@lumeo_hq/openbooks`)
- Output: one JSON document per file, released only if its own arithmetic balances, otherwise a typed refusal with a reason code. Nothing is partially released.
- Status: v0.1 pre-release. Layouts are tested on synthetic fixtures only, not on real bank exports. The README says so.
- Listing: the MCP Registry entry is pending the owner's publish step. Glama listing: [add the Glama link here once the owner has claimed the server, or delete this line].

Happy to change the category or wording if it does not fit the list.
```

## Before opening

- Confirm the repo is public and the README link works.
- Remove the Glama line if no Glama listing exists yet. The research notes that PRs are prioritised when they include a Glama backlink, so claim the Glama listing first (see CHECKLIST.md, day 8-14).
- Open the PR from a fork under the owner's GitHub account. Do not ask anyone to upvote.
