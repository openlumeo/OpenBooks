import type { Metadata } from "next";
import { ArrowUpRight } from "lucide-react";
import { AgentOnboarding } from "@/components/onboard/agent-onboarding";
import styles from "@/components/onboard/onboard.module.css";
import { pageMetadata } from "@/lib/site";

export const metadata: Metadata = pageMetadata({
  title: "Connect your AI agent to Open Books",
  description:
    "Connect Claude, Cursor, VS Code, Codex and other MCP agents to Open Books, then check the install with a sample statement.",
  path: "/get-started",
});

export default function GetStartedPage() {
  return (
    <main id="content" className={styles.page}>
      <header className={styles.intro}>
        <div>
          <h1 className={styles.heading}>Connect Open Books to your AI agent</h1>
          <p className={styles.lede}>Choose your client, install the connection, and verify it with a sample statement.</p>
        </div>
        <a className={styles.workspaceLink} href="/app">Open workspace <ArrowUpRight size={16} aria-hidden="true" /></a>
      </header>
      <nav className={styles.jumps} aria-label="Setup steps">
        <a href="#connect">Connect your agent</a>
        <a href="#check">Check the connection</a>
        <a href="#try">Try a sample prompt</a>
      </nav>
      <AgentOnboarding />
    </main>
  );
}
