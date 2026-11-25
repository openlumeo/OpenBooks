import { AgentQuickStart } from "@/components/onboard/agent-onboarding";
import styles from "./agent-start.module.css";

export function AgentStart() {
  return (
    <section id="agents" aria-labelledby="agents-heading" className={styles.band}>
      <div className={styles.container}>
        <h2 id="agents-heading" className={`t-display t-h2 ${styles.heading}`}>
          Onboard your agent in one paste.
        </h2>
        <p className={`t-lede ${styles.lede}`}>
          Give your agent the line below and it installs Open Books, connects the MCP server and is ready for its first statement.
        </p>
        <AgentQuickStart />
      </div>
    </section>
  );
}
