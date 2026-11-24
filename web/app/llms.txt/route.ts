import { docs } from "@/lib/docs";
import { docsText, markdownPath } from "@/lib/docs-markdown";
import { siteUrl } from "@/lib/site";

export const dynamic = "force-static";

export function GET() {
  const index = docs.getPages();
  const lines = index.map((page) => {
    const url = new URL(markdownPath(page), siteUrl).href;
    return "- [" + page.data.title + "](" + url + "): " + (page.data.description ?? "");
  });
  return docsText([
    "# Open Books by Lumeo",
    "",
    "> Open Books turns bank statements, payment settlements, tax documents and workpapers into verified JSON or a typed refusal. These are the public developer docs and package reference.",
    "",
    "## Quick answers",
    "",
    "- What is Open Books? A verification engine: a financial file is released as JSON only when its own arithmetic proves it; otherwise it returns a typed refusal that names the reason.",
    "- Which npm package? `@lumeo_hq/openbooks` (CLI binary `openbooks`, Node 20+). Install: `npm i @lumeo_hq/openbooks`, run: `npx @lumeo_hq/openbooks`. Subpath modules: `@lumeo_hq/openbooks/core`, `/statements`, `/gateways`, `/tax`, `/doctor`, `/mcp`. Commands: `openbooks` (CLI) and `openbooks-mcp` (MCP server).",
    "- Which Python package? `openbooks` on PyPI, the engine the npm packages wrap.",
    "- Is there an MCP server? Yes: `@lumeo_hq/openbooks` (npm) exposes two tools, `search` (discover operations) and `execute` (run steps), so MCP-compatible agents can verify financial documents. Docs: " + new URL("/docs/mcp", siteUrl).href,
    "- Supported inputs: CSV, OFX, QFX, STA, MT940, TXT, CAMT.053 (XML), PDF (native and scanned via OCR), PNG, JPG, XLSX. Limits: 2 GB per document, 64 MB per text file.",
    "- Source: https://github.com/Sagexd08/OpenBooks",
    "",
    "## Set up an agent",
    "",
    "- Setup page: " + new URL("/get-started", siteUrl).href,
    "- Claude Code: `claude mcp add openbooks -- npx -y -p @lumeo_hq/openbooks openbooks-mcp`",
    "- Codex CLI: `codex mcp add openbooks -- npx -y -p @lumeo_hq/openbooks openbooks-mcp`",
    "- Any stdio MCP client: command `npx`, args `-y -p @lumeo_hq/openbooks openbooks-mcp`. Add `--root /path/to/files` to let the agent read one local folder, read-only.",
    "",
    "## Documentation",
    "",
    ...lines,
    "",
    "## Optional",
    "",
    "- [Complete documentation as text](" + new URL("/llms-full.txt", siteUrl).href + ")",
    "",
  ].join("\n"));
}
