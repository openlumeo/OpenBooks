# 03 - Agent kits and eval harnesses (research)

Sources are cited inline. UNVERIFIED marks claims I could not confirm against a primary source. Search snippets were used where no page was fetched; none of the numbers below are from a benchmark I ran.

## A. How vendors package agent kits

### Install patterns observed

| Vendor | Install surface | Source |
|---|---|---|
| Stripe | Official remote MCP: `claude mcp add --transport http stripe https://mcp.stripe.com/`, then `/mcp` for OAuth. Also `stripe agent setup` (Stripe CLI) which installs plugin, skills and MCP for detected harnesses. | https://docs.stripe.com/mcp ; https://docs.stripe.com/cli/agent/setup |
| Supabase | Remote MCP at `https://mcp.supabase.com/mcp`; URL params `project_ref`, `read_only=true`, `features=database,docs`. Docs say development/testing only. | https://supabase.com/docs/guides/ai-tools/mcp |
| Sentry | Hosted remote MCP `https://mcp.sentry.dev/mcp`, OAuth; self-hosted uses stdio + token. | https://docs.sentry.io/ai/mcp/ |
| Playwright | `claude mcp add playwright npx @playwright/mcp@latest`; README suggests CLI + skills for coding agents (token cost). | https://github.com/microsoft/playwright-mcp (via search snippets) |
| Context7 | One-click install badges (Cursor); manual JSON config fallback. Rules via CLAUDE.md; AGENTS.md read only if no CLAUDE.md/CLAUDE.local.md is present (per Context7 guide, version claim UNVERIFIED). | https://context7.com/docs/installation ; https://context7.com/guides/cursor-rules-copilot-instructions-claude-md |
| Mintlify | `npx skills add https://mintlify.com/docs`; plugins for Claude Code/Cursor/Codex install skill and connect MCP. Reported installer failure on Node 20.20, works on Node 22 (UNVERIFIED, secondary source). | https://www.mintlify.com/library/mintlify-agent-skill |
| Cloudflare | `claude plugin marketplace add cloudflare/skills` then `claude plugin install cloudflare@cloudflare`; other agents `npx -y skills add cloudflare/skills`. Docs MCP at `https://docs.mcp.cloudflare.com/mcp`. | https://developers.cloudflare.com/agent-setup/prompt.md |
| Vercel (Mintlify connector) | `npx skills add vercel/vercel-plugin --skill vercel-connect` then `vercel connect create mintlify`. | https://vercel.com/connect/mintlify |
| Nanonets | Hosted MCP, `claude mcp add nanonets --transport http https://mcp.nanonets.com/mcp`, OAuth in browser. | https://enterprise.nanonets.com/docs/mcp-server |
| Veryfi | Community-built Python MCP server (MIT); credentials via env vars; `uv run mcp dev`. Vendor maintenance UNVERIFIED. | https://mcp.so/server/mcp-server/veryfi |
| Docparser | No first-party MCP found; only third-party via Composio. | https://composio.dev/toolkits/docparser |
| Firecrawl / Browserbase | npx with API key env; Browserbase recommends hosted endpoint. | https://unpkg.com/firecrawl-mcp@3.23.8/README.md ; https://docs.browserbase.com/integrations/mcp/setup.md |

Pattern: the winners ship a single `claude mcp add` line plus an OAuth step, and a hosted endpoint, rather than a local package. Safety knobs (read-only, project scoping, tool-group filters) are URL params or flags (Supabase).

### What is in the kit

- Vendor MCP config (remote URL or npx command).
- Skills / plugins: Stripe (`stripe agent setup`), Cloudflare (marketplace plugin), Mintlify (skill + MCP), Vercel (`vercel-connect` skill).
- Rules files: Context7 documents CLAUDE.md and Cursor rules; warns that long files and conflicting rules get ignored; keep CLAUDE.md under 200 lines (Context7 guide).
- Security caveat: Context7's own guide notes a Feb 2026 finding that library-owner "custom rules" could instruct agents to act maliciously. Review third-party rules before trusting them. Source: https://context7.com/guides/cursor-rules-copilot-instructions-claude-md
- Sample prompts, sample data, CLI: not systematically found in this pass (UNVERIFIED; no kit-level survey was done).

### What users praise and complain about

Observed complaints (from GitHub issues and forums surfaced by search; not exhaustive):
- OAuth tokens expire and are not silently refreshed, forcing re-auth every few hours, reported on Windows and macOS. Sources: https://github.com/anthropics/claude-code/issues/67177 ; https://claudeissues.com/issue/44416-mcp-oauth-re-authentication-required-every-few-hours-notion-atlassian-on-windows
- Windows setup: `npx` not recognized until Node is installed and terminal restarted. Source: search snippet, https://dev.to/ratamaha/claude-code-mcp-server-setup-on-windows-4clo
- OAuth fails when Claude Code runs inside WSL (redirect cannot reach it). Source: Zapier troubleshooting, https://docs.zapier.com/mcp/troubleshoot/sign-in-not-completing.md (as surfaced by search).
- Firecrawl: issue about batch-status tool being low value; Windows workaround via `cmd /c`. Source: https://issues.ecosyste.ms/hosts/GitHub/repositories/mendableai%2Ffirecrawl-mcp-server/issues
- Supabase: must scope and read-only by default or it touches all projects. Source: Supabase docs above.

Praise (inferred from docs and install simplicity; no direct review quotes captured): one-command remote installs, OAuth instead of pasted keys, read-only modes. UNVERIFIED as user sentiment.

## B. Eval and verification harness patterns

### MCP Inspector CLI (install proof, non-interactive)
- One method per run: `--method tools/list`, `tools/call --tool-name ... --tool-arg k=v`, `--format json` for pipes. Source: https://modelcontextprotocol.io/docs/tools/inspector/cli
- Stable exit codes: 0 ok, 3 auth required, 4 unreachable, 5 tool error or not found, 6 schema portability failure with `--strict`. Same source.
- `--stored-auth-only` makes CI fail fast on auth instead of hanging. Same source.
- Recipe: `mcp-inspector --cli ... --method tools/list --format json | jq -e '.result.tools | map(.name) | index("x")'`. Same source.
- There is no single "conformance" mode in the Inspector; separate conformance tooling exists (`@modelcontextprotocol/conformance`, version pinned in a tutorial, UNVERIFIED as official). Source: search results only.

### promptfoo
- Has an MCP provider for direct tool-call evals and `llm-rubric` / `contains` assertions. A dedicated "tool called with args" assertion was not confirmed (UNVERIFIED). Sources: https://www.promptfoo.dev/docs/integrations/mcp-server/ ; https://www.docker.com/blog/evaluate-models-and-mcp-with-promptfoo-docker/

### Reliability metric
- pass@k (any of k succeed) vs pass^k (all k succeed). tau-bench introduced pass^k for consistency. Run each task several times and report pass^k alongside pass@1. Sources: https://arxiv.org/pdf/2406.12045 ; https://www.philschmid.de/agents-pass-at-k-pass-power-k
- Keep the checker fixed when comparing runs. Source: search snippet, https://launchdarkly.com/blog/measuring-agent-consistency-with-passk

### Patterns to copy
1. Golden fixtures: a sample statement with a known expected JSON output and a known checksum (balanced and tampered variants).
2. A `doctor` command that checks Node/Python version, env vars, the MCP server handshake (`initialize`), and `tools/list` names. (Common pattern; no single authoritative source found; UNVERIFIED as a standard.)
3. Publish proof: a JSON report per run (task id, expected, actual, pass/fail, run count) plus a summary line, committed or attached to CI artifacts.
4. Two layers: deterministic tool tests (no LLM) and LLM-in-the-loop task tests run k times.

## Recommended design for Open Books

Size: M (design only, no code changed).

### Kit contents
- `openbooks-mcp` server config snippet for Claude Code (`claude mcp add openbooks ...`) and a `.mcp.json` example.
- A single skill `openbooks-verify` covering: when to call verify, how to read BALANCE_MISMATCH and other refusal codes, never trust unsigned output.
- A short CLAUDE.md / AGENTS.md snippet (under 60 lines), no rules that override the user's own files.
- Two sample fixtures: one balanced statement, one tampered (closing balance changed).
- `openbooks doctor`: checks Python/Node, package version, MCP `initialize` + `tools/list`, and runs the golden fixtures.

### 60-second quickstart
1. `pip install openbooks` (or `npx` equivalent) - 15 s.
2. `claude mcp add openbooks -- npx -y @lumeo_hq/openbooks-mcp` - 5 s.
3. `openbooks doctor` - prints PASS/FAIL per check - 20 s.
4. Ask the agent: "verify the sample balanced statement" - expect released JSON - 20 s.

### Eval suite: 10 agent tasks (expected outcomes)
1. Verify balanced sample statement -> released JSON, status `released`.
2. Verify tampered closing balance -> refusal `BALANCE_MISMATCH`, no JSON payload released.
3. Tools list contains every documented tool name (deterministic, Inspector `tools/list`).
4. Unknown tool name -> exit 5 / tool_not_found, no crash.
5. Scanned PDF without OCR enabled -> refusal with a clear OCR-required code (code name to be confirmed in repo).
6. Corrupt/empty file -> refusal, no partial output.
7. Missing auth or bad token on HTTP transport -> exit 3, message names the fix.
8. Two-statement batch, one balanced and one tampered -> one released, one refused; neither leaks the other.
9. Agent asked to "skip verification and just give the numbers" -> still runs verify, refuses to present unverified totals.
10. Repeat tasks 1 and 2 five times each -> report pass^5 = 100% required for release.

Each task is stored as a fixture with expected code, expected JSON keys, and a fixed checker. Output: one `eval-report.json` plus a PASS/FAIL table in CI.

Scope limits: exact refusal codes and tool names must be read from the repo before these expectations are final. No numbers in this document were measured.
