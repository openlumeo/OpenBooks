# VS Code (Copilot agent mode)

Add to `.vscode/mcp.json` in the workspace:

```json
{
  "servers": {
    "openbooks": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@lumeo_hq/openbooks-mcp"]
    }
  }
}
```

The `servers` shape is the one the research captured. The portable `.mcp.json` form for VS Code is UNVERIFIED.
