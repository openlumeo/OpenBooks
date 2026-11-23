# MCP server best practices (2025-2026) for OpenBooks

Scope: MCP spec, official guidance, and a few third-party listings. Verified pages are cited. Items marked UNVERIFIED were not confirmed from a fetched source.

Spec revisions: the docs index lists a `2026-07-28` revision and a `2025-11-25` revision (https://modelcontextprotocol.io/llms.txt). Everything below marked "2025-11-25" was read from that version. The 2026-07-28 text was not read.

## 1. Tools

- Names: 1-128 chars, ASCII letters, digits, `_`, `-`, `.`, unique per server. Source: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- Fields: `name`, `title`, `description`, `inputSchema`, optional `outputSchema`, `annotations`, `icons`, `execution.taskSupport` (`forbidden` default, `optional`, `required`). Source: same page.
- No-arg tools: use `{"type":"object","additionalProperties":false}`. Source: same page.
- `outputSchema`: servers MUST return conforming `structuredContent`; SHOULD also return the JSON as a TextContent block for backward compatibility. Clients SHOULD validate. Source: same page.
- Annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`): clients MUST treat them as untrusted unless the server is trusted. Source: same page. Default values were not confirmed from the fetched text (UNVERIFIED).
- Errors: protocol errors (JSON-RPC, e.g. unknown tool) vs tool execution errors (`isError: true` in result). Validation and business failures should use `isError: true` with actionable text so the model can retry. Source: same page.
- Security: servers MUST validate inputs, enforce access control, rate-limit, and sanitize outputs. Clients SHOULD confirm sensitive operations and show inputs. Source: same page. The spec says a human should be able to deny invocations.
- Pagination: `tools/list` and `resources/list` use cursors (`nextCursor`). Source: https://modelcontextprotocol.io/specification/2025-11-25/server/tools
- Resource links in tool results (`resource_link`) let large outputs be fetched on demand instead of inlined. Source: same tools page.
- Response size limits, truncation, and "search then execute" patterns: UNVERIFIED from fetched spec text. Treat as community practice.

## 2. Resources and templates

- Declare `resources` capability with `subscribe` and `listChanged` as needed. Source: https://modelcontextprotocol.io/specification/2025-11-25/server/resources
- Resource templates use RFC 6570 URI templates; arguments may be completed via the completion API. Same page.
- Servers MUST validate all resource URIs; access controls SHOULD be enforced; binary must be base64 in `blob`. Same page.
- Annotations: `audience`, `priority` (0-1), `lastModified`. Same page.
- Error code for not found: `-32002`. Same page.

## 3. Prompts, completion, logging, roots, sampling

- Logging, roots, and sampling are DEPRECATED starting with the spec revision expected June 2026. They keep working for one year per version. Source: https://modelcontextprotocol.io/seps/2577-deprecate-roots-sampling-and-logging.md
- Implication: use stderr or OpenTelemetry for logs, tool parameters or resource URIs instead of roots, and direct provider SDKs instead of sampling. Same SEP.
- Prompts and completion: not verified from fetched text (UNVERIFIED).

## 4. Elicitation, progress, cancellation

- Elicitation (form mode and URL mode, SEP-1036 for out-of-band URL mode) exists. Sources: https://modelcontextprotocol.io/seps/1036-url-mode-elicitation-for-secure-out-of-band-intera.md and https://modelcontextprotocol.io/seps/1034--support-default-values-for-all-primitive-types-in.md. Schema rules and security details were not read (UNVERIFIED). Use URL mode for secrets or payment, not form mode.
- Progress and cancellation: the 2025-11-25 progress and cancellation pages were not fetched (404 / timeout). Cancellation guidance per the Streamable HTTP page: disconnect SHOULD NOT be read as cancel; send `CancelledNotification`. Source: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- Long jobs: the Tasks utility (`execution.taskSupport`) is the spec path for task-augmented calls. Sources: https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks.md (listed in the llms.txt index, not read) and SEP-2663 (https://modelcontextprotocol.io/seps/2663-tasks-extension.md, UNVERIFIED content).

## 5. Transports

- stdio: newline-delimited JSON-RPC, no embedded newlines, stdout only for MCP messages, logs on stderr. Clients SHOULD support stdio. Source: https://modelcontextprotocol.io/specification/2025-11-25/basic/transports
- Streamable HTTP: one endpoint supporting POST and GET; must validate `Origin` (403 if invalid); bind to 127.0.0.1 locally; `MCP-Session-Id` header; `MCP-Protocol-Version` header (400 if unsupported); SSE resumability via `Last-Event-ID`. Same page.
- Legacy HTTP+SSE (2024-11-05) is replaced; clients may fall back. Same page.

## 6. Authorization (remote servers)

- Authorization is OPTIONAL. HTTP transports SHOULD follow the spec; stdio SHOULD NOT and reads credentials from the environment. Source: https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- MUST: serve RFC 9728 Protected Resource Metadata with `authorization_servers`; return 401 with `WWW-Authenticate` `resource_metadata`; RFC 8414 or OIDC discovery on the AS. Same page.
- MUST: validate token audience (RFC 8707 resource indicator); reject tokens not issued for this server; never pass through client tokens to upstream APIs. Same page.
- MUST: PKCE with S256 on the client side; refuse if `code_challenge_methods_supported` is absent. Same page.
- Scope errors: 403 with `error="insufficient_scope"` and `scope=...`. Same page.
- Client ID Metadata Documents are SHOULD-supported; DCR is MAY. Same page.

## 7. Security

- Token passthrough and confused deputy are the top MCP-specific risks. Source: authorization page above and https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices (fetch timed out; content UNVERIFIED beyond the authorization page cross-references).
- Prompt injection from document content: the spec requires human confirmation and output sanitization but does not give a document-specific rule. Treat extracted text as untrusted data in tool outputs (UNVERIFIED as a spec rule; general practice).
- Path traversal, SSRF, secrets: the resources page requires URI validation and access control. SSRF guidance was not fetched (UNVERIFIED).

## 8. Registry and metadata

- The official MCP Registry stores `server.json` (name in reverse-DNS form, package or remote locator, env and args). Namespace auth via GitHub or DNS. Preview status. Source: https://modelcontextprotocol.io/registry/about.md
- Server Cards (SEP-2127, HTTP discovery): https://modelcontextprotocol.io/seps/2127-mcp-server-cards.md (content UNVERIFIED).
- The registry does not support private servers. Source: same page.

## 9. Python SDK

- Official SDK ships `mcp.server.fastmcp.FastMCP` (FastMCP 1.x merged into the SDK). Decorators `@mcp.tool()`, `@mcp.prompt()`, resources as GET-like reads. Source (search snippet, not fetched): https://github.com/fastmcp-me/fastmcp-python and https://pypi.org/project/fastmcp/2.10.5/
- Standalone FastMCP v2 docs are at gofastmcp.com per search snippet (UNVERIFIED by fetch). The spec SDK list is at https://modelcontextprotocol.io/docs/2025-11-25/sdk.md (not read).
- The user's stated target is `mcp` package v2. The v2 API was not verified; check the SDK repo before relying on any signature (UNVERIFIED).

## 10. Testing

- MCP Inspector, protocol conformance tests, and tool-use evals with an LLM: recommended in general practice. No fetched official source (UNVERIFIED). Build a fixture set of documents with known answers and score tool selection and argument correctness.

## 11. Exemplary servers (finance, accounting, documents)

Only search-result listings were read. None was verified by opening the repo. Treat as candidates.

1. Invapi `@invapi/mcp-server` (npm): extracts data from PDF and image invoices; creates UBL, CII, ZUGFeRD e-invoices. Needs hosted API key. MIT per listing. https://socket.dev/npm/package/@invapi/mcp-server
2. Papierkram MCP Server (Wagner-Emden-IT-Services): invoices, expenses, PDF download against Papierkram API. MIT per listing. https://mcpservers.org/servers/wagner-emden-it-services/papierkram-mcp-server (linked from search results)
3. tomaxberg/mcp-accounting-server: double-entry bookkeeping, Swedish BAS 2022, SQLite. Closest "accounting" design. License UNVERIFIED. https://lobehub.com/mcp/wolf019-hakan-accounting-mcp (search result was a different listing; repo link UNVERIFIED)
4. theluckystrike MCP Invoice: invoice generation to PDF with tax lines. Free tier limit per listing. https://mcpservers.org/servers/mcp-zovo-one-s-invoice (listing; repo UNVERIFIED)
5. markslorach/invoice-mcp: PDF invoices from natural language via React PDF. License not stated in listing. https://mcpservers.org/id/servers/markslorach/invoice-mcp
6. Official modelcontextprotocol/servers reference set (filesystem, fetch, git, memory): UNVERIFIED in this session. Use as pattern reference for roots-free file access.

## 12. Top 20 checklist for a financial-document verification server (ranked by impact)

1. Structured output: `outputSchema` plus `structuredContent` with a text fallback for every verification result.
2. Verdict-first results: each check returns status, reason code, evidence (page, bbox, quoted value), and confidence.
3. `isError: true` with actionable text for bad input (wrong file type, unreadable PDF), never a protocol error for those.
4. Read-only annotations on all verify and extract tools (`readOnlyHint: true`, `openWorldHint: false`).
5. Strict input schemas with `additionalProperties: false`, enums for check types, and size and page limits.
6. Path and file access confined to an allowlisted upload directory; reject `..` and symlinks.
7. Treat document text as untrusted data; never let extracted text change tool selection (prompt-injection guard in output framing).
8. Pagination via cursor on large findings lists; cap results per call and return `nextCursor`.
9. Response size budget: summarize by default, return `resource_link` URIs for full evidence pages.
10. Stable, deterministic IDs for findings so repeated runs are diffable.
11. Idempotent verification: same input and version gives the same result; expose the checker version.
12. Long jobs (OCR, large batches): task-augmented execution or progress notifications, plus cancellation support.
13. Redact PII and account numbers in logs; logs to stderr for stdio.
14. Remote deployment: OAuth 2.1 resource server with RFC 9728 metadata, audience-checked tokens, no token passthrough.
15. Scope-based access: separate read-only verify scope from any write scope; step-up on `insufficient_scope`.
16. Origin validation and localhost binding for Streamable HTTP.
17. Versioned tool names or `title` changes documented; `listChanged` only if the set actually changes.
18. Eval suite: labeled documents with expected verdicts; score tool choice, argument validity, and verdict accuracy per release.
19. MCP Inspector and protocol conformance run in CI on every release.
20. Registry `server.json` with accurate package or remote locator, and an explicit statement of what the server does not verify (limitations).

## Gaps

- Not read: 2025-11-25 progress, cancellation, logging, pagination, elicitation pages (404 or timeout); security best practices page (timeout); 2026-07-28 revision text.
- Not verified: Python `mcp` v2 API signatures; exemplary server repos and licenses.
