# 09. Product moat and UX for the Open Books harness

Status: research only. No code changed. Date of research: 2026-11-24.
Labels: VERIFIED (read from a primary page in this session), SNIPPET (only seen in search-result text, not fetched), VENDOR (vendor's own claim), UNVERIFIED (could not confirm). Confidence is High, Medium or Low.

Fetch notes: Codex skills docs (developers.openai.com/codex/skills) and Braintrust docs (www.braintrust.dev/docs/evaluate) redirected to other hosts that were not fetched, so those claims are SNIPPET or UNVERIFIED. The Cline and Goose key-storage claims come from third-party mirrors, not official docs.

## Ranked shortlist

1. P0: Keychain-first, env-var-reference key entry with a test-connection step. Adopt. Low risk, reuses existing `openbooks.providers.toml` design (env var names only).
2. P0: Per-document evidence view that shows the balance proof and the typed refusal code. Adopt. This is the product itself, not a generic dashboard.
3. P0: Typed refusal explanations linked to the `openbooks://guide/refusals` resource. Adopt.
4. P1: Benchmark runner plus run history with provider comparison, borrowing the Promptfoo and Inspect viewer patterns. Experiment.
5. P1: Skill and plugin packaging so users can fork and customise the workflow. Adopt the existing plugin layout, do not build a marketplace yet.
6. P2: Hosted skills marketplace and hosted leaderboard features beyond the current submit page. Reject for now; revisit after community fixtures exist.

## 1. Onboarding, config, keys, skills and UI in comparable kits

| Kit | What it does (source) | Label | Confidence |
|---|---|---|---|
| Hermes Agent (Nous Research) | Terminal, desktop, messaging and IDE front ends; `hermes setup` wizard, `hermes model`, `hermes doctor`; config in `~/.hermes/config.yaml` described as holding settings but not secrets; 40+ bundled skills in `~/.hermes/skills/`. Source: https://hermes-agent.nousresearch.com/docs/index.html and https://hermes-agent.nousresearch.com/docs/llms.txt | SNIPPET (landing page and index; third-party guides not verified) | Medium |
| Goose (Block) | Recommends the OS keyring (Keychain, Credential Manager, Secret Service). Secrets fall back to a plaintext `~/.config/goose/secrets.yaml` when `GOOSE_DISABLE_KEYRING` is set or the keyring errors. Env vars override config. Custom OpenAI-compatible providers as JSON files. Sources: https://block.github.io/goose/docs/getting-started/providers and https://block.github.io/goose/docs/guides/environment-variables (SNIPPET only, not fetched) | SNIPPET | Medium |
| Cline (VS Code) | Keys reportedly kept in VS Code SecretStorage. No official doc confirmed this. MCP settings reportedly in an unencrypted JSON file that Settings Sync can upload. Sources: https://docs.cline.bot/api/authentication (SNIPPET), third-party guides at https://fast.io/resources/cline-settings-json-config-guide/ and https://netwrix.com/en/resources/blog/ai-coding-assistant-credential-storage-risks/ | UNVERIFIED (storage backend); SNIPPET (MCP file risk) | Low to Medium |
| Claude Code plugins | A plugin is a directory with `.claude-plugin/plugin.json` plus skills, agents, hooks and `.mcp.json`. Marketplaces are catalogs (`marketplace.json`), not hosted stores. Install scope is user, project or local. Plugins run with the user's privileges, and the docs point to a security page. Enabled plugins add skill descriptions to every session's context. Source: https://code.claude.com/docs/en/plugins (VERIFIED) | VERIFIED | High |
| Codex skills | Skill and plugin packaging exists; the official page redirected to learn.chatgpt.com/docs/build-skills, which was not fetched. | UNVERIFIED (details) | Low |
| OpenHands | Moved to Agent Canvas, a browser client connecting to Agent Server backends (local, self-hosted or cloud). The fetched page did not cover API key setup. Source: https://docs.openhands.dev/ (VERIFIED for the architecture only) | VERIFIED (architecture) | Medium |

Pattern across kits: a setup wizard or doctor command, config file without secrets, secrets in OS keyring or a provider-specific store, and a plugin or skill folder with a manifest. Open Books already has most of this in `harness/README.md` (doctor, `--root`, client configs, `openbooks.providers.toml` with env var names only).

Hypothesis (UNVERIFIED benefit): users trust a kit more when it states exactly where each secret lives. Test with 5 users in a usability session.

## 2. Bring-your-own-key UX best practice

Guidance to apply, with sources:

- Never persist keys in plain text in project files. Source: OWASP Secrets Management Cheat Sheet, https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html (SNIPPET only; the search result did not show the exact plaintext wording, so the specific sentence is UNVERIFIED).
- Reference env var names, not values, in config. Supported by Promptfoo docs that show `apiKey: ${ENV_VAR}` references and warn that pasted credentials may be saved in local artifacts. Source: https://www.promptfoo.dev/docs/faq/ (SNIPPET).
- Keep secrets out of results. Open Books `bench/CONTRACT.md` already redacts keys (VERIFIED in repo, `harness/bench/CONTRACT.md`).
- Keyring first, env var second, file fallback last with a visible warning. Goose's design shows the fallback is plaintext (SNIPPET); Open Books should make the plaintext path opt-in and labelled.
- Test-connection: a no-document call that checks auth and reports the provider's model list or quota, never sending a customer document. Hypothesis, UNVERIFIED benefit.
- Cost preview: show page count and estimated price before a remote OCR call. Open Books already has `--max-cost-usd` for the bench (VERIFIED, `harness/README.md`). Extend the same idea to OCR pages.
- Per-provider fallback: the existing plan (`docs/harness/PLAN.md` section 2.6) is all-or-nothing per document and never mixes engines. Keep it. Show the chosen provider on every result.
- Remote privacy gate: `allow_remote = false` by default, stated in the UI. Consistent with the local-first rule in `harness/CLAUDE.md` (VERIFIED).

Verdict: adopt keyring plus env-var reference model. Confidence Medium, because the keyring library choice (Python `keyring` package) is UNVERIFIED for this repo.

## 3. What a harness web UI should contain

Real examples, with what each does (SNIPPET unless noted):

- Langfuse: self-hosted tracing, datasets, experiments, LLM-as-judge in the free self-host edition. Per-project roles are not in the free tier. Sources: https://langfuse.com/docs and https://langfuse.com/resources/engineering/clarifications.md (VENDOR claims).
- Promptfoo: `promptfoo view` opens a web UI for results; `report` command for red-team output. Source: https://www.promptfoo.dev/docs/red-team/quickstart/ (SNIPPET).
- Inspect AI: `inspect view` launches a log viewer with a results summary, sample expansion, scorer detail and token usage; `inspect view bundle` produces a static site for hosting. Source: https://inspect.aisi.org.uk/log-viewer.html and https://inspect.aisi.org.uk/reference/inspect_view.html (SNIPPET).
- Braintrust: experiments compared side by side. Could not fetch the page; UNVERIFIED for specifics.

Recommended harness screens (wireframe level):

1. Setup screen. Left: provider list (tesseract default, easyocr, azure, google, aws, mistral, llamaparse). Each row: status (keyring, env, missing), Test connection button, remote toggle (off by default), price per page. Footer: where each secret is stored.
2. Run history. Table: run id, time, provider, model, documents, released count, refused count, refusal codes, overall score. Filter by provider and refusal code. Export JSON (`bench-result.v1.json`).
3. Provider comparison. Same tasks across providers in columns. Rows: release accuracy, field accuracy, p95 latency, cost, memory. Highlight disagreements (one provider released, another refused).
4. Document evidence view (core screen). Left: page image with word boxes. Right: parsed rows, opening, closing, sum of transactions, balance gate result (equation shown with numbers), confidence per row, method (`pdf_text`, `ocr`, `ocr+model`), provider id. Bottom: hash of the file and the proof JSON. A refused document shows the refusal code, the failing check, and no released figures.
5. Refusal explanation panel. Code, plain-language cause, what the user can change (for example a missing opening balance from a trusted source), link to the refusals guide. Never shows a "verified" badge.
6. Benchmark runner. Choose provider, model, task subset, max cost; cost estimate before run; live progress; canary and safety flags.
7. Skills and plugins. List installed skills with their file path and the tools they call; enable or disable per project.

## 4. Defensible moats and what is easy to copy

| Asset | Defensibility | Why | Confidence |
|---|---|---|---|
| Balance-proof format (versioned, schema-constrained evidence with `method` enum) | High if published and adopted by others | Proof is checkable by third parties; copying the format is easy, but gaining adoption needs fixtures | Medium |
| Typed refusals (stable codes, documented in `openbooks://guide/refusals`) | Medium | Easy to copy the names; hard to copy the test corpus behind each code | Medium |
| Local-first privacy with `--root` and remote gate | Medium | Competitors (Reducto, Mistral OCR, cloud APIs) are cloud-first by design; the gap is structural (VENDOR claims, not checked) | Low to Medium |
| Community fixtures and public benchmark with server re-scoring | High once volume exists | Network effect; the server re-scores from answers and engine outcomes (VERIFIED in `harness/README.md`) | Medium |
| Skills marketplace | Low now | Claude Code marketplaces are catalogs (VERIFIED); copying is trivial | High |
| Engine code (parsers, column geometry) | Low | Open source; easy to fork | High |

Easy to copy: the UI shell, the plugin layout, the provider adapter interface, the keyring pattern.
Hard to copy: a corpus of labelled statements with ground-truth outcomes, and years of refusal-code history.

Caveat: "competitors are cloud-first" needs a check against each vendor's privacy page before any marketing claim. Mark UNVERIFIED until then.

## Prioritised feature list

P0 (do first)
- Key entry with env-var references and keyring, test-connection, remote gate off by default.
- Document evidence view with balance equation and method and provider labels.
- Refusal explanation panel tied to refusal codes.
- Proof JSON export with a stable schema version and file hash.

P1 (after P0 works)
- Run history with provider comparison and disagreement highlighting.
- Benchmark runner with cost estimate.
- Plugin packaging of the existing skill and commands, per-project enable or disable.
- Community fixture template and a public contribution guide.

P2 (later, needs data)
- Hosted skills marketplace.
- Team roles and shared run history (Langfuse notes roles are a paid tier; check cost before copying).
- Live cost dashboards across providers.

## Validation to run

- Five-user usability test of the key setup flow (benefit hypothesis, UNVERIFIED).
- Check OWASP cheat sheet and Codex skills docs directly before citing them externally.
- Fetch Braintrust docs at docs.braintrust.dev/evaluate and confirm the comparison UI claims.
- Confirm each competitor's privacy and data-retention page before any "cloud-first" claim.
