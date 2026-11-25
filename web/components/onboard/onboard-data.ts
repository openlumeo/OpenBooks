export type AgentId =
  | "claude-code"
  | "claude-desktop"
  | "cursor"
  | "vscode"
  | "codex"
  | "goose"
  | "gemini-cli"
  | "cline"
  | "chatgpt"
  | "muse"
  | "grok"
  | "grok-bot"
  | "hermes"
  | "openclaw"
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
  logo?: string;
  video?: string;
  art: ArtGradient;
  cards: InstallCard[];
};

export type TryIcon = "shield" | "x" | "folder" | "search" | "list" | "activity";

export type TryPrompt = {
  id: string;
  title: string;
  icon: TryIcon;
  prompt: string;
};

export const SERVER_NAME = "openbooks";
export const PACKAGE_NAME = "@lumeo_hq/openbooks";
export const SITE_LLMS_URL = "https://openbooks.openlumeo.com/llms.txt";
export const KIT_HREF = "/downloads/openbooks-harness.zip";
export const KIT_TEXT = "Includes MCP config for every client, a verify skill, sample statements and a self-check.";

export const STDIO_COMMAND = "npx";
export const STDIO_ARGS = ["-y", "-p", PACKAGE_NAME, "openbooks-mcp"] as const;
export const STDIO_SERVER = { command: STDIO_COMMAND, args: STDIO_ARGS } as const;

export const MCP_SERVERS_JSON = JSON.stringify({ mcpServers: { [SERVER_NAME]: STDIO_SERVER } }, null, 2);

function encodeBase64(text: string): string {
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
    logo: "/brand/agents/claude-code.png",
    art: { from: "#f1b394", to: "#d9785a" },
    cards: [
      { id: "add", label: "Add Open Books", code: CLAUDE_CODE_ADD },
      {
        id: "add-folder",
        label: "Add with a read-only folder",
        code: `${CLAUDE_CODE_ADD} --root /path/to/files`,
      },
    ],
  },
  ...[
    { id: "chatgpt", name: "ChatGPT", monogram: "C", logo: "/brand/agents/chatgpt.png", art: { from: "#d9ece4", to: "#10a37f" } },
    { id: "muse", name: "Muse", monogram: "M", logo: "/brand/agents/muse.svg", video: "/brand/agents/muse-hatch.mp4", art: { from: "#d6e4ff", to: "#1d6bff" } },
    { id: "grok", name: "Grok", monogram: "G", logo: "/brand/agents/grok.png", art: { from: "#dfe3e8", to: "#1c1f24" } },
    { id: "grok-bot", name: "Grok Bot", monogram: "B", logo: "/brand/agents/grok-bot.png", art: { from: "#e2e2e2", to: "#16181b" } },
    { id: "hermes", name: "Hermes Agent", monogram: "H", logo: "/brand/agents/hermes.png", art: { from: "#d4e4f6", to: "#3d6fb0" } },
    { id: "openclaw", name: "OpenClaw", monogram: "O", logo: "/brand/agents/openclaw.png", art: { from: "#f7b9b0", to: "#d6433a" } },
  ].map((agent) => ({
    ...agent,
    id: agent.id as AgentId,
    cards: [
      { id: "generic-json", label: "mcpServers JSON", code: MCP_SERVERS_JSON },
      { id: "stdio", label: "Raw stdio command", code: `${STDIO_COMMAND} ${STDIO_ARGS.join(" ")}` },
    ],
  })),
  {
    id: "claude-desktop",
    name: "Claude Desktop",
    monogram: "D",
    logo: "/brand/agents/claude-desktop.png",
    art: { from: "#f1b394", to: "#d9785a" },
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
    logo: "/brand/agents/cursor.png",
    art: { from: "#e6e6ea", to: "#2a2b30" },
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
    art: { from: "#cfe6f7", to: "#1f7ac8" },
    cards: [{ id: "add-mcp", label: "Run in a terminal", code: VSCODE_ADD }],
  },
  {
    id: "codex",
    name: "Codex CLI",
    monogram: "X",
    logo: "/brand/agents/codex.png",
    art: { from: "#e0dcff", to: "#5b4be0" },
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
    logo: "/brand/agents/goose.png",
    art: { from: "#eadcf8", to: "#7a4fc2" },
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
    logo: "/brand/agents/gemini-cli.png",
    art: { from: "#d3e4fb", to: "#4285f4" },
    cards: [{ id: "settings", label: "~/.gemini/settings.json", code: MCP_SERVERS_JSON }],
  },
  {
    id: "cline",
    name: "Cline",
    monogram: "L",
    logo: "/brand/agents/cline.png",
    art: { from: "#f4e8c6", to: "#c9962e" },
    cards: [{ id: "settings", label: "cline_mcp_settings.json", code: MCP_SERVERS_JSON }],
  },
  {
    id: "other",
    name: "Other MCP client",
    monogram: "O",
    art: { from: "#dcebe3", to: "#3f8f6a" },
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
    prompt: "Use Open Books to verify the sample statement with opening balance 1000.00 and show me the proof.",
  },
  {
    id: "see-refusal",
    title: "See a refusal",
    icon: "x",
    prompt: "Use Open Books to verify the sample statement without an opening balance and explain why it is refused.",
  },
  {
    id: "check-local-file",
    title: "Check a local file",
    icon: "folder",
    prompt: "Use Open Books to verify statements/january.csv in my approved folder and list any failed checks.",
  },
  {
    id: "explain-refusal",
    title: "Explain a refusal",
    icon: "search",
    prompt: "Explain the BALANCE_MISMATCH refusal from Open Books and what I should check.",
  },
  {
    id: "inspect-transactions",
    title: "Inspect transactions",
    icon: "list",
    prompt: "Use Open Books to show the first 5 transactions of the last verified statement with their evidence.",
  },
  {
    id: "check-install",
    title: "Check my install",
    icon: "activity",
    prompt: CHECK_PROMPT,
  },
];
