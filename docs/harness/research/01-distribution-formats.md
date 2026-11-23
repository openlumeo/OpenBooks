# Distribution formats for an AI-client harness (Open Books)

Research date: 2026-11-23. Items marked UNVERIFIED were not confirmed in a fetched source.

## 1. Claude Code plugins and marketplaces

Sources: [Plugin manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference), [Marketplace reference](https://code.claude.com/docs/en/plugins/marketplace-reference)

Layout (default locations, all at plugin root):
```
openbooks-plugin/
  .claude-plugin/plugin.json   (optional manifest)
  skills/<name>/SKILL.md
  commands/*.md
  agents/*.md
  hooks/hooks.json
  .mcp.json
```
- `plugin.json`: `name` is the only required key (kebab-case). Other keys include `version`, `description`, `author` (object, `name` required), `homepage`, `repository`, `license`, `keywords`, `mcpServers`, `userConfig`.
- Manifest example (verbatim from docs, trimmed):
```json
{
  "name": "deploy-tools",
  "version": "1.2.0",
  "description": "Deployment commands, a review agent, and a status monitor",
  "mcpServers": {
    "deploy-api": { "command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"] }
  }
}
```
- `.mcp.json` is loaded at plugin root; `${CLAUDE_PLUGIN_ROOT}` resolves to the installed plugin path.
- `userConfig` prompts users on enable; `"sensitive": true` stores the value in secure storage. Referenced as `${user_config.KEY}`.
- `marketplace.json` at `.claude-plugin/marketplace.json`. Required: `name`, `owner` (object, `name` required), `plugins` (array of entries with `name` and `source`).
- Plugin source types: relative path (`"./plugins/x"`), `github` (`repo`, `ref`, `sha`), `url`, `git-subdir`, `npm`, `archive` (`sha256`), `command`.
- Install (user side): `/plugin marketplace add <owner/repo or path>`, then `/plugin install <plugin>@<marketplace>`. Verify the exact slash-command syntax in your Claude Code version: UNVERIFIED for the install line (the fetched pages cite `plugin@marketplace` ids but I did not capture the exact command text).
- Validation: `claude plugin validate ./my-plugin`, `--strict` for CI.
- Skills and commands ship inside the plugin, so one plugin can carry the skill, the MCP server config and a slash command.
- Discovery: a public catalog exists (Anthropic directory) and any git repo can be a marketplace. Reserved marketplace names are enforced (do not use `claude-*`, `anthropic-*`).

## 2. Agent Skills open format (SKILL.md)

Source: [agentskills.io specification](https://agentskills.io/specification)

```
skill-name/
  SKILL.md        (required)
  scripts/ references/ assets/   (optional)
```
- Frontmatter required: `name` (1-64 chars, lowercase a-z 0-9 and hyphens, no leading/trailing/double hyphen, must equal parent directory name), `description` (1-1024 chars).
- Optional: `license`, `compatibility` (max 500), `metadata` (string map), `allowed-tools` (experimental, space-separated).
- Minimal:
```markdown
---
name: openbooks-verify
description: Verify bank statements, settlements and tax documents into proven JSON or a typed refusal. Use when the user asks to verify or reconcile a financial document.
---
```
- Validate with `skills-ref validate ./my-skill` (per spec).
- Discovery per client: Claude Code loads skills from plugins and `.claude/skills/`; other clients discover in their own paths (UNVERIFIED per client; not fetched).

## 3. Claude Desktop MCP bundles (.mcpb)

Source: [mcpb MANIFEST.md](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md), [mcpb README](https://github.com/modelcontextprotocol/mcpb/blob/main/README.md)

- Bundle file extension `.mcpb` (older `.dxt` are now `.mcpb`).
- `manifest.json` required fields: `manifest_version` (0.3 per spec), `name`, `version` (semver), `description`, `author` (`name` required), `server` (`type`: node|python|binary|uv, `entry_point`, `mcp_config`).
- `user_config` options: `type` (string|number|boolean|directory|file), `title`, `description`, `required`, `default`, `multiple`, `sensitive`, `min`/`max`. Referenced as `${user_config.KEY}` in `mcp_config`.
- CLI: `npm install -g @anthropic-ai/mcpb`, then `mcpb init` and `mcpb pack`. The README fetched did not document `validate`, `sign` or `verify` (UNVERIFIED; see CLI.md in the repo).
- Signing: UNVERIFIED. Not in fetched pages.
- Install (user): double-click the `.mcpb` in Claude Desktop (UNVERIFIED wording). Claude Code also accepts `.mcpb` paths in plugin `mcpServers` (per [manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference)).

## 4. Cursor

Sources: [Install links](https://cursor.com/docs/context/mcp/install-links), [Plugins reference](https://cursor.com/docs/reference/plugins) (via search, not fetched)

- MCP deeplink (verified):
```
cursor://anysphere.cursor-deeplink/mcp/install?name=$NAME&config=$BASE64_ENCODED_CONFIG
```
  `config` = base64 of JSON.stringify of the inner server object (no name key), e.g. `{"command":"npx","args":["-y","..."]}`.
- Manual `mcp.json` (verified shape from the page): `{"postgres": {"command": "npx", "args": [...]}}` under `mcpServers`/name key; file location `.cursor/mcp.json` (UNVERIFIED path).
- Rules: `.cursor/rules/*.mdc` with YAML frontmatter (description, globs, alwaysApply). Plain `.md` without frontmatter is ignored (per search summary, [cursor.com/docs/rules](https://cursor.com/docs/rules)).
- Plugins: `.cursor-plugin/plugin.json`, rules in `rules/`, multi-plugin `.cursor-plugin/marketplace.json`. Team-submitted and manually reviewed (per search summary; UNVERIFIED in detail).

## 5. VS Code (Copilot agent mode)

Source: [MCP servers](https://code.visualstudio.com/docs/copilot/customization/mcp-servers), [MCP configuration](https://code.visualstudio.com/docs/copilot/reference/mcp-configuration)

- Editor-managed `.vscode/mcp.json` (deprecated for new setups per page):
```json
{ "servers": { "playwright": { "type": "stdio", "command": "npx", "args": ["-y", "@playwright/mcp@latest"] } } }
```
- Portable form for new setups: workspace-root `.mcp.json` with `mcpServers` (per page; exact schema not captured).
- CLI install: `code --add-mcp '{"name":"playwright","type":"stdio","command":"npx","args":["-y","@playwright/mcp@latest"]}'` (source: the MCP config page as summarized).
- Install deeplink `vscode:mcp/install?...`: UNVERIFIED. Not found in fetched pages; do not rely on it without checking.
- Badge URLs: UNVERIFIED.

## 6. OpenAI Codex CLI

Source: [Codex MCP docs](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) (redirect from developers.openai.com/codex/mcp)

- `~/.codex/config.toml` or project `.codex/config.toml` (trusted projects):
```toml
[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]

[mcp_servers.context7.env]
MY_ENV_VAR = "MY_ENV_VALUE"
```
- Remote: `[mcp_servers.<name>] url = "https://..."`, `bearer_token_env_var`, `http_headers`.
- Install: `codex mcp add openbooks -- npx -y @lumeo_hq/openbooks-mcp` (pattern from docs; package name is an example, verify it exists).
- AGENTS.md discovery rules: UNVERIFIED (page not captured).

## 7. Gemini CLI extensions

Source: [Extensions reference](https://geminicli.com/docs/extensions/reference/)

- Directory: `<home>/.gemini/extensions/<name>/`; root must contain `gemini-extension.json`.
- Manifest required in practice: `name` (lowercase, dashes, matches dir name), `version`, `description`. Optional: `mcpServers`, `contextFileName`, `excludeTools`, `settings`.
- Layout: `GEMINI.md`, `commands/*.toml`, `hooks/hooks.json`, `skills/<name>/SKILL.md`, `agents/*.md` (preview), `policies/*.toml`.
- Install: `gemini extensions install <github-url-or-local-path> [--ref <ref>] [--auto-update]` (not in interactive mode).
- Distribution: GitHub repo URL; no central deeplink captured.

## 8. Goose

Source: [Goose extensions](https://goose-docs.ai/docs/getting-started/using-extensions/)

- Deeplink (verified):
  - stdio: `goose://extension?cmd=npx&arg=-y&arg=%40scope%2Fpkg&timeout=300&id=<id>&name=<name>&description=<desc>` (`cmd` one of jbang, npx, uvx, goosed, docker; `timeout` documented as required; URL-encode all values).
  - remote: `goose://extension?url=<url>&type=streamable_http&id=...&name=...&description=...`
- Config `~/.config/goose/config.yaml`:
```yaml
extensions:
  openbooks:
    name: Open Books
    cmd: npx
    args: [-y @lumeo_hq/openbooks-mcp]
    enabled: true
    envs: {}
    type: stdio
    timeout: 300
```

## 9. Windsurf, Cline, Zed

- Cline (search summary, [docs.cline.bot MCP marketplace](https://docs.cline.bot/mcp/mcp-marketplace)): config `cline_mcp_settings.json` under VS Code globalStorage; `mcpServers` object keyed by server name. Marketplace listing is curated by Cline (submission process UNVERIFIED). Deeplink: UNVERIFIED.
- Windsurf: docs redirect to docs.devin.ai; content not captured. `mcp_config.json` location and deeplink: UNVERIFIED.
- Zed: MCP servers ship inside a Zed extension via `extension.toml` `[context_servers.<name>]` plus a Rust `context_server_command` implementation ([Zed MCP extensions](https://zed.dev/docs/extensions/mcp-extensions)). Users can also add servers in settings (exact key not captured, UNVERIFIED). Zed extensions are not a one-file install for a Node/Python server.

## 10. Recommended kit layout (one repo)

```
openbooks-harness/
  .claude-plugin/
    plugin.json                 # Claude Code plugin manifest (name: openbooks)
    marketplace.json            # self-hosted marketplace, source "./"
  skills/openbooks-verify/SKILL.md
  commands/verify.md
  .mcp.json                     # {"mcpServers": {"openbooks": {"command":"npx","args":["-y","@lumeo_hq/openbooks-mcp"]}}}
  manifest.json                 # .mcpb manifest for Claude Desktop (user_config for API key)
  gemini-extension.json         # + GEMINI.md, skills/ (same SKILL.md)
  AGENTS.md                     # Codex, Cursor, others read it (UNVERIFIED for Cursor)
  .cursor/rules/openbooks.mdc   # alwaysApply/description frontmatter
  .cursor-plugin/plugin.json    # optional Cursor plugin
  .vscode/mcp.json              # VS Code (or .mcp.json for portable form)
  goose/config-snippet.yaml
  zed/extension.toml            # optional, larger effort
  install/README.md             # per-client deeplinks and install commands
```
Single source of truth: the MCP server config and SKILL.md. Generate per-client files with a script in CI so the server args never drift. Badge/deeplink generation: Cursor base64 link and Goose goose:// link are verified; VS Code and Windsurf deeplinks are not, so ship them as copy-paste config until verified.

## Open items
- Confirm Claude Desktop signing and `mcpb validate/sign` (UNVERIFIED).
- Confirm VS Code `vscode:mcp/install` deeplink (UNVERIFIED).
- Confirm Windsurf, Codex AGENTS.md discovery, and Cursor `mcp.json` path.
