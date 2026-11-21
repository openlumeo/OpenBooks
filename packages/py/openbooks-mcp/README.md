# Open Books MCP

Verify financial documents and inspect their released data, evidence and
assertions from an MCP-compatible agent. The server exposes two tool
definitions, `search` and `execute`. An execution can process a document and
inspect only the needed parts in the same ordered batch.

Install the wheel using Python 3.11 or newer. Point the MCP client at
`python -m openbooks_mcp --root /path/to/financial/files` using the interpreter
where the wheel is installed. Omit `--root` for synthetic samples and small
in-memory uploads.

See the [Open Books MCP guide](https://openbooks.lumeo.co.in/docs/mcp) for
downloads, agent configuration, batch examples and private HTTP setup.
