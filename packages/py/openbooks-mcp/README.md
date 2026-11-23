# Open Books MCP

mcp-name: io.github.sagexd08/openbooks-mcp

Open Books MCP is a Model Context Protocol server that lets an AI agent verify
financial documents. A bank statement, payment settlement, tax document or
workpaper comes back as one proven JSON document, or as a typed refusal that
says why. A file is released only when its own arithmetic proves it.

## Install

Requires Python 3.11 or newer.

```bash
pip install openbooks-mcp
pip install "openbooks-mcp[scan]"
```

The `scan` extra adds OCR for scanned PDFs and images.

## Connect a client

Claude Desktop, Cursor and other MCP clients use the same shape. Use the
interpreter where the package is installed:

```json
{
  "mcpServers": {
    "openbooks": {
      "command": "python",
      "args": ["-m", "openbooks_mcp", "--root", "/path/to/financial/files"]
    }
  }
}
```

Omit `--root` to work with synthetic samples and small in-memory uploads.

## Tools

| Tool | Purpose |
|---|---|
| `search` | Discover the available operations and their details. |
| `execute` | Run an ordered batch of steps: process a document, then inspect only the data, evidence or assertions you need. |

Example: ask the agent to "verify statement.pdf and show any failed
assertions". It calls `execute` once with a process step followed by an inspect
step.

## Limits

- Documents up to 2 GB, text files (CSV, OFX, QFX, MT940, TXT) up to 64 MB.
- Inline uploads over MCP are capped at 1 MB; use `--root` for larger files.
- Supported inputs: CSV, OFX, QFX, STA, MT940, TXT, PDF, PNG, JPG, XLSX.

## Links

- [Open Books MCP guide](https://openbooks.lumeo.co.in/docs/mcp): downloads, agent configuration, batch examples and private HTTP setup.
- [Website](https://openbooks.lumeo.co.in)
- [Source](https://github.com/Sagexd08/OpenBooks)
- npm CLI: `@lumeo_hq/openbooks`
