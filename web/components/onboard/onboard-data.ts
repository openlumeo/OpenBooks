export type AgentId =
  | "claude-code"
  | "claude-desktop"
  | "cursor"
  | "vscode"
  | "codex"
  | "goose"
  | "gemini-cli"
  | "cline"
  | "other";

export type ArtGradient = { from: string; to: string };

export type InstallCard = {
  id: string;
  label: string;
  code: string;
  note?: string;
  deeplink?: { label: string; href: string };
};

export type AgentSetup = {
  id: AgentId;
  name: string;
  monogram: string;
  art: ArtGradient;
  cards: InstallCard[];
};

export type TryIcon = "shield" | "x" | "folder" | "search" | "list" | "activity";

export type TryPrompt = {
  id: string;
  title: string;
  icon: TryIcon;
  hue: number;
  prompt: string;
};

export const SERVER_NAME = "openbooks";
export const PACKAGE_NAME = "@lumeo_hq/openbooks";
export const SITE_LLMS_URL = "https://openbooks.lumeo.co.in/llms.txt";
export const KIT_HREF = "/downloads/openbooks-harness.zip";
export const KIT_TEXT = "Includes MCP config for every client, a verify skill, sample statements and a self-check.";

export const STDIO_COMMAND = "npx";
export const STDIO_ARGS = ["-y", "-p", PACKAGE_NAME, "openbooks-mcp"] as const;
export const STDIO_SERVER = { command: STDIO_COMMAND, args: STDIO_ARGS } as const;

export const MCP_SERVERS_JSON = JSON.stringify({ mcpServers: { [SERVER_NAME]: STDIO_SERVER } }, null, 2);

export function encodeBase64(text: string): string {
  return btoa(text);
}

export function cursorDeeplink(): string {
  const config = encodeBase64(JSON.stringify(STDIO_SERVER));
  return `cursor://anysphere.cursor-deeplink/mcp/install?name=${SERVER_NAME}&config=${encodeURIComponent(config)}`;
}

export const GOOSE_DEEPLINK =
  "goose://extension?cmd=npx&arg=-y&arg=-p&arg=%40lumeo_hq%2Fopenbooks&arg=openbooks-mcp&timeout=300&id=openbooks&name=Open%20Books&description=Verify%20financial%20documents";

const CLAUDE_CODE_ADD = `claude mcp add ${SERVER_NAME} -- npx -y -p ${PACKAGE_NAME} openbooks-mcp`;
const CODEX_ADD = `codex mcp add ${SERVER_NAME} -- npx -y -p ${PACKAGE_NAME} openbooks-mcp`;
const VSCODE_ADD = `code --add-mcp '{"name":"${SERVER_NAME}","type":"stdio","command":"npx","args":["-y","-p","${PACKAGE_NAME}","openbooks-mcp"]}'`;

export const AGENT_CHAT_PROMPT = `set up Open Books — ${SITE_LLMS_URL}`;
export const CHECK_PROMPT = "Run the Open Books doctor and tell me if my setup is healthy.";
export const HEALTHY_TEXT = "A healthy install reports healthy: true and a released sample statement.";
export const RUNTIME_TEXT = "Requires Node.js 20 or newer. The server runs with npx, so nothing else needs installing.";

export const AGENTS: readonly AgentSetup[] = [
  {
    id: "claude-code",
    name: "Claude Code",
    monogram: "C",
    art: { from: "#1f5f4a", to: "#7cc7a4" },
    cards: [
      { id: "add", label: "Add Open Books", code: CLAUDE_CODE_ADD },
      {
        id: "add-folder",
        label: "Add with a read-only folder",
        code: `${CLAUDE_CODE_ADD} --root /path/to/files`,
      },
    ],
  },
  {
    id: "claude-desktop",
    name: "Claude Desktop",
    monogram: "D",
    art: { from: "#7a3b2e", to: "#e3a27e" },
    cards: [
      {
        id: "config",
        label: "Merge into claude_desktop_config.json",
        code: MCP_SERVERS_JSON,
        note: "macOS: ~/Library/Application Support/Claude/claude_desktop_config.json. Windows: %APPDATA%\\Claude\\claude_desktop_config.json. Then restart Claude Desktop.",
      },
    ],
  },
  {
    id: "cursor",
    name: "Cursor",
    monogram: "U",
    art: { from: "#2d3a6b", to: "#8fa6e8" },
    cards: [
      {
        id: "deeplink",
        label: "One-click install",
        code: cursorDeeplink(),
        deeplink: { label: "Add to Cursor", href: cursorDeeplink() },
      },
      { id: "project-file", label: ".cursor/mcp.json", code: MCP_SERVERS_JSON },
    ],
  },
  {
    id: "vscode",
    name: "VS Code",
    monogram: "V",
    art: { from: "#1b4f7a", to: "#6fb6e6" },
    cards: [{ id: "add-mcp", label: "Run in a terminal", code: VSCODE_ADD }],
  },
  {
    id: "codex",
    name: "Codex CLI",
    monogram: "X",
    art: { from: "#3b3a2a", to: "#d7cf8a" },
    cards: [
      { id: "add", label: "Run in a terminal", code: CODEX_ADD },
      {
        id: "toml",
        label: "~/.codex/config.toml",
        code: `[mcp_servers.${SERVER_NAME}]\ncommand = "${STDIO_COMMAND}"\nargs = ["-y", "-p", "${PACKAGE_NAME}", "openbooks-mcp"]`,
      },
    ],
  },
  {
    id: "goose",
    name: "Goose",
    monogram: "G",
    art: { from: "#4a2a6b", to: "#c3a2ef" },
    cards: [
      {
        id: "deeplink",
        label: "One-click install",
        code: GOOSE_DEEPLINK,
        deeplink: { label: "Add to Goose", href: GOOSE_DEEPLINK },
      },
    ],
  },
  {
    id: "gemini-cli",
    name: "Gemini CLI",
    monogram: "Γ",
    art: { from: "#1d4d5c", to: "#8fd3e0" },
    cards: [{ id: "settings", label: "~/.gemini/settings.json", code: MCP_SERVERS_JSON }],
  },
  {
    id: "cline",
    name: "Cline",
    monogram: "L",
    art: { from: "#5a4a1c", to: "#e9c46a" },
    cards: [{ id: "settings", label: "cline_mcp_settings.json", code: MCP_SERVERS_JSON }],
  },
  {
    id: "other",
    name: "Other MCP client",
    monogram: "O",
    art: { from: "#2b3a33", to: "#9dc7b2" },
    cards: [
      { id: "generic-json", label: "mcpServers JSON", code: MCP_SERVERS_JSON },
      { id: "stdio", label: "Raw stdio command", code: `${STDIO_COMMAND} ${STDIO_ARGS.join(" ")}` },
    ],
  },
];

export const DEFAULT_AGENT_ID: AgentId = "claude-code";

export function agentById(id: AgentId): AgentSetup {
  const agent = AGENTS.find((entry) => entry.id === id);
  if (!agent) throw new Error(`Unknown agent: ${id}`);
  return agent;
}

export const TRY_PROMPTS: readonly TryPrompt[] = [
  {
    id: "verify-sample",
    title: "Verify a sample",
    icon: "shield",
    hue: 150,
    prompt: "Use Open Books to verify the sample statement with opening balance 1000.00 and show me the proof.",
  },
  {
    id: "see-refusal",
    title: "See a refusal",
    icon: "x",
    hue: 210,
    prompt: "Use Open Books to verify the sample statement without an opening balance and explain why it is refused.",
  },
  {
    id: "check-local-file",
    title: "Check a local file",
    icon: "folder",
    hue: 265,
    prompt: "Use Open Books to verify statements/january.csv in my approved folder and list any failed checks.",
  },
  {
    id: "explain-refusal",
    title: "Explain a refusal",
    icon: "search",
    hue: 25,
    prompt: "Explain the BALANCE_MISMATCH refusal from Open Books and what I should check.",
  },
  {
    id: "inspect-transactions",
    title: "Inspect transactions",
    icon: "list",
    hue: 300,
    prompt: "Use Open Books to show the first 5 transactions of the last verified statement with their evidence.",
  },
  {
    id: "check-install",
    title: "Check my install",
    icon: "activity",
    hue: 115,
    prompt: CHECK_PROMPT,
  },
];
