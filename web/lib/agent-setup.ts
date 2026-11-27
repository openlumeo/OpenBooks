export const AGENT_CLIENTS = ["claude", "chatgpt", "codex", "grok", "hermes"] as const;
export type AgentClient = typeof AGENT_CLIENTS[number];

const AGENT_SETUP_PATH = "/api/agent/mcp";
export const AGENT_SETUP_URL = "https://books.openlumeo.com" + AGENT_SETUP_PATH;
export const SETUP_TOKEN = /^[A-Za-z0-9_-]{32}$/;
export const SETUP_MINUTES = 10;
