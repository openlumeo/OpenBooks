import type { Metadata } from "next";
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
      <h1 className={styles.heading}>Welcome! Getting started</h1>
      <AgentOnboarding />
    </main>
  );
}
