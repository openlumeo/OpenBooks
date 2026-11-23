# Claude Desktop bundle (.mcpb)

`manifest.json` uses the fields in the research (`manifest_version`, `name`, `version`, `description`, `author`, `server` with `type`, `entry_point`, `mcp_config`). The `node` server type is listed in the research. The `entry_point` value `server/index.js` is UNVERIFIED: this kit does not ship a server file, and the npm package is built separately. Do not treat the bundle as ready until the entry point is confirmed.

Packing: the research confirmed `npm install -g @anthropic-ai/mcpb`, then `mcpb init` and `mcpb pack`. `npx @anthropic-ai/mcpb pack` is UNVERIFIED. Signing, `validate` and `verify` are UNVERIFIED and omitted.
