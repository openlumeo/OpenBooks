"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  Activity,
  FileSearch,
  FolderOpen,
  ListChecks,
  ShieldCheck,
  ShieldX,
  type LucideIcon,
} from "lucide-react";
import {
  AGENTS,
  AGENT_CHAT_PROMPT,
  CHECK_PROMPT,
  DEFAULT_AGENT_ID,
  HEALTHY_TEXT,
  KIT_HREF,
  KIT_TEXT,
  RUNTIME_TEXT,
  TRY_PROMPTS,
  agentById,
  type AgentId,
  type AgentSetup,
  type InstallCard,
  type TryIcon,
  type TryPrompt,
} from "./onboard-data";
import styles from "./onboard.module.css";

const COPIED_MS = 1600;

const TRY_ICONS: Record<TryIcon, LucideIcon> = {
  shield: ShieldCheck,
  x: ShieldX,
  folder: FolderOpen,
  search: FileSearch,
  list: ListChecks,
  activity: Activity,
};

function fallbackCopy(text: string): boolean {
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try {
    return document.execCommand("copy");
  } catch {
    return false;
  } finally {
    area.remove();
  }
}

async function writeClipboard(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      return fallbackCopy(text);
    }
  }
  return fallbackCopy(text);
}

type Announce = (message: string) => void;

function CopyButton({ text, label, announce, tone = "dark" }: { text: string; label: string; announce: Announce; tone?: "dark" | "text" }) {
  const [feedback, setFeedback] = useState<"copied" | "failed" | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function handleCopy() {
    const ok = await writeClipboard(text);
    setFeedback(ok ? "copied" : "failed");
    announce(ok ? `${label} copied` : `Could not copy ${label}. Select and copy the text manually.`);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setFeedback(null), COPIED_MS);
  }

  const className = tone === "dark" ? styles.copyDark : styles.copyText;
  const action = feedback === "copied" ? "Copied" : feedback === "failed" ? "Retry" : "Copy";
  return (
    <button type="button" className={className} onClick={handleCopy} aria-label={`${action} ${label}`}>
      {action}
    </button>
  );
}

function CodeRow({ text, label, announce }: { text: string; label: string; announce: Announce }) {
  return (
    <div className={styles.codeRow}>
      <pre className={styles.code}>
        <code>{text}</code>
      </pre>
      <CopyButton text={text} label={label} announce={announce} />
    </div>
  );
}

function Monogram({ agent }: { agent: AgentSetup }) {
  if (agent.logo) {
    return (
      <span className={styles.logoChip} aria-hidden="true">
        <img src={agent.logo} alt="" width={28} height={28} className={styles.logoImg} />
      </span>
    );
  }
  return (
    <span className={styles.monogram} aria-hidden="true">
      {agent.monogram}
    </span>
  );
}


function AgentPicker({ selectedId, onSelect }: { selectedId: AgentId; onSelect: (id: AgentId) => void }) {
  const pickerId = useId();
  return (
    <div className={styles.picker}>
      <label className={styles.cardTitle} htmlFor={pickerId}>Your AI agent</label>
      <select id={pickerId} className={styles.pickerButton} value={selectedId}
        onChange={(event) => {
          const selected = AGENTS.find((agent) => agent.id === event.target.value);
          if (selected) onSelect(selected.id);
        }}>
        {AGENTS.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
      </select>
    </div>
  );
}

function InstallCardView({ card, announce }: { card: InstallCard; announce: Announce }) {
  return (
    <article className={styles.card}>
      <h3 className={styles.cardTitle}>{card.label}</h3>
      <CodeRow text={card.code} label={card.label} announce={announce} />
      {card.note && <p className={styles.note}>{card.note}</p>}
      {card.deeplink && (
        <a className={styles.linkButton} href={card.deeplink.href}>
          {card.deeplink.label}
        </a>
      )}
    </article>
  );
}

function PromptCard({ prompt, announce }: { prompt: TryPrompt; announce: Announce }) {
  const Icon = TRY_ICONS[prompt.icon];
  return (
    <article className={styles.promptCard}>
      <div className={styles.promptBody}>
        <div className={styles.promptHead}>
          <Icon size={16} aria-hidden="true" />
          <h3 className={styles.promptTitle}>{prompt.title}</h3>
          <CopyButton text={prompt.prompt} label={prompt.title} announce={announce} tone="text" />
        </div>
        <p className={styles.promptText}>{prompt.prompt}</p>
      </div>
    </article>
  );
}

const QUICK_AGENT_IDS: readonly AgentId[] = ["claude-code", "grok", "grok-bot", "openclaw", "hermes"];

export function AgentQuickStart({ workspaceHref = "/app" }: { workspaceHref?: string }) {
  const [announcement, setAnnouncement] = useState("");
  const agents = QUICK_AGENT_IDS.map(agentById);

  return (
    <div className={styles.quick}>
      <p role="status" aria-live="polite" className={styles.sr}>
        {announcement}
      </p>
      <div className={styles.quickLogos} aria-label="Works with">
        {agents.map((agent) => (
          <span key={agent.id} className={styles.quickAgent}>
            <Monogram agent={agent} />
            {agent.name}
          </span>
        ))}
      </div>
      <p className={styles.quickLabel}>Paste this in your agent&apos;s chat</p>
      <CodeRow text={AGENT_CHAT_PROMPT} label="chat setup line" announce={setAnnouncement} />
      <div className={styles.quickActions}>
        <a className={styles.quickPrimary} href={workspaceHref}>
          Open workspace
        </a>
        <a className={styles.quickSecondary} href="/get-started">
          All agents and setup steps
        </a>
      </div>
    </div>
  );
}

export function AgentOnboarding() {
  const [agentId, setAgentId] = useState<AgentId>(DEFAULT_AGENT_ID);
  const [announcement, setAnnouncement] = useState("");
  const agent = agentById(agentId);

  return (
    <div className={styles.root}>
      <p role="status" aria-live="polite" className={styles.sr}>
        {announcement}
      </p>

      <section id="connect" className={`${styles.card} ${styles.connectCard}`} aria-labelledby="connect-title">
        <div className={styles.setupGrid}>
          <div className={styles.setupAside}>
            <h2 id="connect-title" className={styles.stepTitle}>Connect your agent</h2>
            <AgentPicker selectedId={agentId} onSelect={setAgentId} />
          </div>

          <div className={styles.details}>
            <div className={styles.instruction}>
              <h3 className={styles.cardTitle}>Paste this in your agent’s chat</h3>
              <CodeRow text={AGENT_CHAT_PROMPT} label="chat setup prompt" announce={setAnnouncement} />
            </div>
            <details className={styles.disclosure} key={agentId}>
              <summary>Manual setup and file access for {agent.name}</summary>
              <div className={styles.details}>
                {agent.cards.map((card) => (
                  <InstallCardView key={card.id} card={card} announce={setAnnouncement} />
                ))}
                <p className={styles.note}>
                  Use <code>--root &lt;folder&gt;</code> to grant read-only access to one local folder.
                  Without a root, the agent can use samples and uploads up to 1 MiB.
                </p>
                <p className={styles.note}>
                  Private HTTP mode requires <code>OPENBOOKS_MCP_TOKEN</code> with at least 32 ASCII characters.
                </p>
                <p className={styles.note}>{RUNTIME_TEXT}</p>
              </div>
            </details>
          </div>
        </div>
      </section>

      <section id="check" className={styles.card} aria-labelledby="check-title">
        <h2 id="check-title" className={styles.stepTitle}>Check the connection</h2>
        <p className={styles.caption}>{HEALTHY_TEXT}</p>
        <CodeRow text={CHECK_PROMPT} label="connection check prompt" announce={setAnnouncement} />
      </section>

      <section id="try" className={styles.examples} aria-labelledby="examples-title">
        <h2 id="examples-title" className={styles.stepTitle}>Try a sample prompt</h2>
        <div className={styles.promptGrid}>
          {TRY_PROMPTS.map((prompt) => (
            <PromptCard key={prompt.id} prompt={prompt} announce={setAnnouncement} />
          ))}
        </div>
      </section>

      <a className={`${styles.card} ${styles.kit}`} href={KIT_HREF} download>
        <span>
          <span className={styles.cardTitle}>Download the agent kit</span>
          <span className={styles.note}>{KIT_TEXT}</span>
        </span>
        <span className={styles.linkButton}>Download</span>
      </a>
    </div>
  );
}
