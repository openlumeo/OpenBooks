"use client";

import { useEffect, useId, useState } from "react";
import { Check, Clipboard, Link2, LoaderCircle } from "lucide-react";
import { AGENT_CLIENTS, AGENT_SETUP_URL, type AgentClient } from "@/lib/agent-setup";
import styles from "./agent-onboarding.module.css";

const clients: Record<AgentClient, { name: string; instruction: string; command?: string }> = {
  claude: {
    name: "Claude",
    instruction: "In Claude Code, register the server with this command. In Claude's connector settings, you can add the same URL as a custom connector.",
    command: "claude mcp add --transport http openbooks-setup " + AGENT_SETUP_URL,
  },
  chatgpt: {
    name: "ChatGPT",
    instruction: "Enable developer mode if your workspace allows it. Add a custom app using this MCP URL, choose No authentication, and enable the app in your chat.",
  },
  codex: {
    name: "Codex",
    instruction: "Register the server with Codex CLI. Start a new session after adding it.",
    command: "codex mcp add openbooks-setup --url " + AGENT_SETUP_URL,
  },
  grok: {
    name: "Grok",
    instruction: "In Grok's Connectors, choose New Connector, then Custom. Enter this MCP URL and enable the connector.",
  },
  hermes: {
    name: "Hermes",
    instruction: "Add this entry to your Hermes config and restart the agent.",
    command: "mcp_servers:\n  openbooks_setup:\n    url: " + AGENT_SETUP_URL,
  },
};

type Pairing = { watch: string; code: string; expiresAt: string };
type Phase = "ready" | "starting" | "waiting" | "connected" | "expired" | "error";

function prompt(code: string) {
  return [
    "Verify my connection to Open Books.",
    "Use the connected Open Books setup MCP server at " + AGENT_SETUP_URL + ".",
    'Call its confirm_connection tool once with {"code":"' + code + '"}.',
    "Tell me whether the tool confirmed the connection. Only report success if the tool confirms it.",
  ].join("\n");
}

async function request(body: object, signal?: AbortSignal) {
  const response = await fetch("/api/agent/setup", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) throw new Error("Setup status is unavailable");
  return response.json();
}

export function AgentOnboarding() {
  const id = useId();
  const [client, setClient] = useState<AgentClient>("claude");
  const [pairing, setPairing] = useState<Pairing | null>(null);
  const [phase, setPhase] = useState<Phase>("ready");
  const [copied, setCopied] = useState(false);
  const [pollError, setPollError] = useState(false);
  const profile = clients[client];

  useEffect(() => {
    if (!pairing || phase !== "waiting") return;
    const controller = new AbortController();
    let timer = 0;
    async function check() {
      if (!pairing || controller.signal.aborted) return;
      if (Date.parse(pairing.expiresAt) <= Date.now()) {
        setPhase("expired");
        return;
      }
      try {
        const { status } = await request({ action: "status", watch: pairing.watch }, controller.signal);
        if (controller.signal.aborted) return;
        setPollError(false);
        if (status === "connected" || status === "expired") {
          setPhase(status);
          return;
        }
      } catch {
        if (controller.signal.aborted) return;
        setPollError(true);
      }
      timer = window.setTimeout(() => void check(), 4_000);
    }
    timer = window.setTimeout(() => void check(), 1_000);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [pairing, phase]);

  function select(next: AgentClient) {
    setClient(next);
    setPairing(null);
    setPhase("ready");
    setCopied(false);
    setPollError(false);
  }

  async function copyPrompt() {
    let current = pairing;
    if (!current || phase === "expired") {
      setPhase("starting");
      setCopied(false);
      setPollError(false);
      try {
        current = await request({ action: "start", client });
        if (!current) throw new Error("Missing setup challenge");
        setPairing(current);
        setPhase("waiting");
      } catch {
        setPhase("error");
        return;
      }
    }
    try {
      await navigator.clipboard.writeText(prompt(current.code));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <section className={`not-prose ${styles.panel}`} aria-label="Agent setup">
      <fieldset className={styles.clients} disabled={phase === "starting"}>
        <legend>Choose an agent</legend>
        {AGENT_CLIENTS.map((entry) => (
          <label key={entry} className={styles.client}>
            <input type="radio" name={id + "-client"} checked={entry === client} onChange={() => select(entry)} />
            <img src={`/brand/agents/${entry}.png`} alt="" width={32} height={32} />
            <span>{clients[entry].name}</span>
          </label>
        ))}
      </fieldset>

      <div className={styles.setup}>
        <h3>Connect {profile.name}</h3>
        <p>{profile.instruction}</p>
        <pre className={styles.command}><code>{profile.command ?? AGENT_SETUP_URL}</code></pre>
        <button
          type="button"
          className={styles.copy}
          onClick={() => void copyPrompt()}
          disabled={phase === "starting" || phase === "connected"}
        >
          {phase === "starting" ? <LoaderCircle size={17} aria-hidden="true" /> : <Clipboard size={17} aria-hidden="true" />}
          {phase === "starting" ? "Preparing prompt…" : phase === "expired" ? "Start new setup" : "Copy setup prompt"}
        </button>
        <div className={styles.status} role="status">
          {phase === "connected" ? <><Check size={17} aria-hidden="true" /> Open Books setup connection verified.</>
            : phase === "waiting" ? <><Link2 size={17} aria-hidden="true" /> {pollError
                ? "Connection status is temporarily unavailable. Retrying…"
                : (copied ? "Prompt copied. Paste it into your agent. " : "Copy the prompt below. ") + "Waiting for the agent’s MCP call."}</>
            : phase === "expired" ? "This setup code expired. Start a new setup to try again."
            : phase === "error" ? "Setup is temporarily unavailable. Try copying again."
            : ""}
        </div>
        {pairing && phase === "waiting" && !copied && (
          <textarea
            className={styles.prompt}
            aria-label="Setup prompt"
            readOnly
            value={prompt(pairing.code)}
            onFocus={(event) => event.currentTarget.select()}
          />
        )}
      </div>
    </section>
  );
}
