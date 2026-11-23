# Publish @lumeo_hq/openbooks-mcp to the official MCP Registry

Status: DRAFT. Manual owner steps. Nothing here has been run.

Source of the steps: docs/seo/research/04-dev-discovery-channels.md (section 2a). The registry is in preview; confirm flags with `mcp-publisher --help` before running.

## Facts from the repo

- Server manifest: `packages/js/mcp/server.json`. Name `io.github.Sagexd08/openbooks-mcp`, version `0.2.3`, npm package `@lumeo_hq/openbooks-mcp`, transport `stdio`.
- npm ownership marker: `packages/js/mcp/package.json` has `"mcpName": "io.github.Sagexd08/openbooks-mcp"`. The registry verifies npm packages through this field, not through a README line.
- Version: `packages/js/mcp/package.json` says `0.2.3`. The npm package must be published at that version before the registry listing points to it.
- The Python package `openbooks-mcp` on PyPI is retired. Its `server.json` was removed; do not publish a PyPI release.

## Open decision before publishing: name casing

The namespace uses the exact GitHub login, io.github.Sagexd08/openbooks-mcp, in server.json and in package.json `mcpName`; they must match each other. Run `mcp-publisher validate` to confirm.

## Steps (owner)

1. Install the publisher CLI (method per the registry quickstart: https://modelcontextprotocol.io/registry/quickstart).
2. Publish the npm package at `0.2.3` from `packages/js/mcp` (owner runs this; not done by the agent). Confirm the npm page shows the package and that `npm view @lumeo_hq/openbooks-mcp mcpName` prints the namespace.
3. Validate the manifest:
   ```bash
   cd packages/js/mcp
   mcp-publisher validate
   ```
4. Log in with GitHub and publish:
   ```bash
   mcp-publisher login github
   mcp-publisher publish
   ```
5. Confirm the listing:
   ```bash
   curl "https://registry.modelcontextprotocol.io/v0.1/servers?search=io.github.Sagexd08/openbooks-mcp"
   ```
   Use the exact name you chose in the casing step.

## Notes

- `server.json` `$schema` points to the 2025-07-09 schema. The research template uses 2025-12-11. Use whatever `mcp-publisher init` generates for the current schema, then keep the repo's other fields.
- Environment variables: none are listed in server.json. The HTTP token (`OPENBOOKS_MCP_TOKEN`) applies only to HTTP mode, not to the stdio package entry.
- Remote-only servers use a `remotes` array instead of `packages`. Not applicable here.
- Do not publish until the owner has picked the name casing and the npm package at 0.2.3 is live with `mcpName` set.
