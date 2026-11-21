# Open Books security and reliability audit

## Scope

Reviewed the web API boundaries, the Python engine request and proof flow, the downloadable MCP server, the agent setup transport and the publishable Node.js packages. Verified behavior with synthetic financial data and a disposable PostgreSQL instance. The audit covered source and dependency advisories for the code under review.

## Findings and fixes

| Priority | Finding | Resolution |
| --- | --- | --- |
| High | The web tier followed redirects on authenticated engine requests. Its custom tunnel header could be reused across origins. | Engine requests now share a single fetch helper that rejects redirects. |
| High | The web engine relay accepted upstream HTML and other media types on the application origin. | The relay permits JSON, event streams and binary sample downloads. Unexpected representations receive a generic gateway error. |
| Medium | Public gateway errors exposed internal endpoint details. Model request errors could return provider diagnostics directly. | User-facing gateway and model messages identify the failure without upstream details. |
| Medium | On Netlify, a missing platform IP header fell back to a generic forwarded address. | Netlify uses the platform header or a shared fallback bucket. |
| Medium | The Node.js wrapper bounded subprocess logs while reading each proof file without a byte limit. | Proofs must be regular files and are read under a separate bounded stream. The default is 64 MiB per document. |
| Medium | Malformed engine discovery and diagnosis output could throw unrelated exceptions or report the wrong installation error. | The wrappers validate engine-info and doctor results and report typed `bad_output` failures. The discovery cache is bounded and respects the configured timeout. |

## Agent onboarding verification

The setup-only MCP endpoint accepts a short-lived code. The database keeps hashes of the connection and watch tokens, checks expiration, and applies confirmation atomically. A setup receipt indicates that the tool call succeeded. It conveys no identity, account access, file scope or private MCP credentials.

The sandbox test runs the MCP initialization, tool discovery and confirmation through the Streamable HTTP handler against an isolated PostgreSQL database. It also verifies receipt isolation, expiration, repeated confirmation, bounded request bodies and expired-row cleanup. The downloadable Python MCP has separate tests for scoped reads, uploads, batch execution and bearer authentication.

## Dependency review

The npm audit output associates GHSA-6cpc-mj5c-m9rq with the local workspace directory named `cli`. The advisory concerns the npm package named `cli`, which is absent from the published Open Books dependency graph. Inspect the published dependency names when repeating this check. [GitHub advisory](https://github.com/advisories/GHSA-6cpc-mj5c-m9rq)

The web production dependency scan returned zero advisories. The Python sandbox initially flagged its pip installer. After upgrading pip, the scan reported zero known vulnerabilities in the installed dependencies it could match to PyPI. The direct-download Open Books MCP package was checked at the source and with protocol tests.

## Release checks

- 65 web tests, including the isolated PostgreSQL setup and MCP receipt tests.
- 67 npm workspace tests, including engine-output limits and ordered decisions with per-file options.
- Six downloadable MCP tests.
- All six npm tarballs installed together in a fresh directory. The installed CLI released the synthetic bank statement.
