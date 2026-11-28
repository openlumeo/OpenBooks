"use client";

import { useEffect, useId, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
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
  const style = { "--mono-from": agent.art.from, "--mono-to": agent.art.to } as CSSProperties;
  if (agent.logo) {
    return (
      <span className={styles.logoChip} aria-hidden="true">
        <img src={agent.logo} alt="" width={28} height={28} className={styles.logoImg} />
      </span>
    );
  }
  return (
    <span className={styles.monogram} style={style} aria-hidden="true">
      {agent.monogram}
    </span>
  );
}


function AgentPicker({ selectedId, onSelect }: { selectedId: AgentId; onSelect: (id: AgentId) => void }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const optionRefs = useRef<(HTMLLIElement | null)[]>([]);
  const listId = useId();
  const selectedIndex = Math.max(0, AGENTS.findIndex((agent) => agent.id === selectedId));
  const selected = agentById(selectedId);

  useEffect(() => {
    if (open) optionRefs.current[active]?.focus();
  }, [open, active]);

  useEffect(() => {
    if (!open) return;
    function handlePointer(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handlePointer);
    return () => document.removeEventListener("mousedown", handlePointer);
  }, [open]);

  function openList() {
    setActive(selectedIndex);
    setOpen(true);
  }

  function closeList(returnFocus: boolean) {
    setOpen(false);
    if (returnFocus) buttonRef.current?.focus();
  }

  function choose(agent: AgentSetup | undefined) {
    if (!agent) return;
    onSelect(agent.id);
    closeList(true);
  }

  function handleButtonKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      openList();
    }
  }

  function handleListKey(event: KeyboardEvent<HTMLUListElement>) {
    const count = AGENTS.length;
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) event.preventDefault();
    if (event.key === "ArrowDown") setActive((index) => (index + 1) % count);
    else if (event.key === "ArrowUp") setActive((index) => (index - 1 + count) % count);
    else if (event.key === "Home") setActive(0);
    else if (event.key === "End") setActive(count - 1);
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(AGENTS[active]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      closeList(true);
    } else if (event.key === "Tab") closeList(false);
  }

  return (
    <div className={styles.pickerWrap} ref={rootRef}>
      <button
        ref={buttonRef}
        type="button"
        className={styles.pickerButton}
        aria-label={`AI agent: ${selected.name}`}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        onClick={() => (open ? closeList(false) : openList())}
        onKeyDown={handleButtonKey}
      >
        <span className={styles.pickerValue}>
          <Monogram agent={selected} />
          {selected.name}
        </span>
        <span className={styles.chevron} aria-hidden="true">▾</span>
      </button>
      {open && (
        <ul id={listId} role="listbox" aria-label="AI agent" className={styles.listbox} onKeyDown={handleListKey}>
          {AGENTS.map((agent, index) => (
            <li
              key={agent.id}
              ref={(node) => {
                optionRefs.current[index] = node;
              }}
              role="option"
              aria-selected={agent.id === selectedId}
              tabIndex={-1}
              className={styles.option}
              onClick={() => choose(agent)}
            >
              <Monogram agent={agent} />
              {agent.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

const DOT_FIELD = Array.from({ length: 25 }, (_, index) => index);

function ArtPanel({ agent }: { agent: AgentSetup }) {
  const style = { "--art-from": agent.art.from, "--art-to": agent.art.to } as CSSProperties;
  const isMascot = agent.id === "claude-code";
  return (
    <div className={styles.art} style={style} data-agent={agent.id}>
      <span className={styles.artDots} aria-hidden="true" />
      {isMascot ? (
        <>
          <span className={styles.artBlock} aria-hidden="true" />
          <span className={styles.artEyeLeft} aria-hidden="true" />
          <span className={styles.artEyeRight} aria-hidden="true" />
        </>
      ) : (
        <>
          {agent.id === "chatgpt" && (
            <span className={styles.artDotField} aria-hidden="true">
              {DOT_FIELD.map((index) => (
                <span key={index} style={{ "--dot-i": index } as CSSProperties} />
              ))}
            </span>
          )}
          <span className={styles.artRing} aria-hidden="true" />
          {agent.video && (
            <video className={styles.artVideo} src={agent.video} autoPlay muted loop playsInline aria-hidden="true" />
          )}
          {agent.logo ? (
            <img src={agent.logo} alt="" width={160} height={160} className={styles.artHero} />
          ) : (
            <span className={styles.artHeroMono}>{agent.monogram}</span>
          )}
        </>
      )}
      <span className={styles.artName}>{agent.name}</span>
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
      <div className={styles.promptArt} data-tone={prompt.icon} aria-hidden="true">
        <span className={styles.promptArtIcon}>
          <Icon size={28} />
        </span>
      </div>
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

      <section className={styles.card} aria-labelledby="step-one">
        <div className={styles.setupGrid}>
          <div className={styles.picker}>
            <div className={styles.stepHead}>
              <span className={styles.pill} aria-hidden="true">1</span>
              <h2 id="step-one" className={styles.stepTitle}>Set up your</h2>
            </div>
            <AgentPicker selectedId={agentId} onSelect={setAgentId} />
            <ArtPanel key={agent.id} agent={agent} />
          </div>

          <div className={styles.details}>
            <p className={styles.caption}>Setting up Open Books for {agent.name}</p>

            <article className={styles.card}>
              <h3 className={styles.cardTitle}>In your agent&apos;s chat, send:</h3>
              <CodeRow text={AGENT_CHAT_PROMPT} label="chat setup line" announce={setAnnouncement} />
            </article>

            {agent.cards.map((card) => (
              <InstallCardView key={card.id} card={card} announce={setAnnouncement} />
            ))}

            <article className={styles.card}>
              <h3 className={styles.cardTitle}>Choose what your agent can read</h3>
              <p className={styles.note}>
                Add <code>--root &lt;folder&gt;</code> to let the agent read local files from one folder, read-only.
                Without a root, it uses the sample data and uploads up to 1 MiB.
              </p>
              <p className={styles.note}>
                Private HTTP mode needs the OPENBOOKS_MCP_TOKEN environment variable, 32+ ASCII characters.
              </p>
            </article>

            <article className={styles.card}>
              <h3 className={styles.cardTitle}>Check it works</h3>
              <CodeRow text={CHECK_PROMPT} label="check prompt" announce={setAnnouncement} />
              <p className={styles.note}>{HEALTHY_TEXT}</p>
            </article>

            <article className={`${styles.card} ${styles.quiet}`}>
              <p className={styles.note}>{RUNTIME_TEXT}</p>
            </article>
          </div>
        </div>
      </section>

      <section className={styles.card} aria-labelledby="step-two">
        <div className={styles.stepHead}>
          <span className={styles.pill} aria-hidden="true">2</span>
          <h2 id="step-two" className={styles.stepTitle}>Try it out</h2>
        </div>
        <p className={styles.caption}>Copy an example below and send it to your agent.</p>
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
