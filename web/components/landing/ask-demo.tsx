// Section 6 "ask": an EXAMPLE conversation. Every figure comes from ask-data.ts, which
// was computed by code over the engine's released document (see that file's header).
// The collapsed tool lines are native <details>, so they work with JS off.
import { ChevronRight } from "lucide-react";
import { ReconPanel } from "./reconciliation";
import { Section } from "./section";
import { ASK_EXAMPLE } from "./ask-data";
import styles from "./ask-demo.module.css";

type ToolRow = { id: string; date: string; description: string; amount: string };

type ToolCall = {
  direction: "debit" | "credit";
  count: number;
  sum: string;
  rows: ToolRow[];
};

const DEBIT_CALL: ToolCall = {
  direction: "debit",
  count: ASK_EXAMPLE.debit.count,
  sum: ASK_EXAMPLE.debit.sum,
  rows: ASK_EXAMPLE.debit.ids.map((id) => ({
    id,
    date: ASK_EXAMPLE.debit.date,
    description: ASK_EXAMPLE.debit.description,
    amount: ASK_EXAMPLE.debit.sum,
  })),
};

const CREDIT_CALL: ToolCall = {
  direction: "credit",
  count: ASK_EXAMPLE.credit.count,
  sum: ASK_EXAMPLE.credit.sum,
  rows: ASK_EXAMPLE.credit.ids.map((id) => ({
    id,
    date: ASK_EXAMPLE.credit.date,
    description: ASK_EXAMPLE.credit.description,
    amount: ASK_EXAMPLE.credit.sum,
  })),
};

function rowsLabel(count: number): string {
  return `${count} ${count === 1 ? "row" : "rows"}`;
}

function ToolLine({ call }: { call: ToolCall }) {
  const summary = `QUERY · direction=${call.direction} → ${rowsLabel(call.count)}, ${call.sum} ${ASK_EXAMPLE.currency}`;
  return (
    <details className={styles.tool}>
      <summary className={styles.toolSummary}>
        <ChevronRight aria-hidden="true" size={14} strokeWidth={1.75} className={styles.chevron} />
        <span>{summary}</span>
      </summary>
      <div className={styles.toolBody}>
        <code className={styles.code}>
          {`query_transactions({ file: "${ASK_EXAMPLE.file}", direction: "${call.direction}" })`}
        </code>
        <div
          className={`lp-scroll lp-figure ${styles.scroll}`}
          tabIndex={0}
          role="region"
          aria-label={`Records matched by direction ${call.direction}`}
        >
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Record</th>
                <th scope="col">Date</th>
                <th scope="col">Description</th>
                <th scope="col" className={styles.num}>
                  Amount {ASK_EXAMPLE.currency}
                </th>
              </tr>
            </thead>
            <tbody>
              {call.rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td>{row.date}</td>
                  <td>{row.description}</td>
                  <td className={styles.num}>{row.amount}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </details>
  );
}

export function AskDemo() {
  const { debit, credit, file, currency, batchId, question } = ASK_EXAMPLE;
  return (
    <Section id="ask" heading="Ask in plain language. The totals come from code.">
      <p className={`t-lede ${styles.lede}`}>
        The model explains and cites. Every sum and count is computed over the released data with exact decimals, and every
        answer names the file and the record.
      </p>
      <ReconPanel title={file}>
        <div className={styles.conversation}>
          <div className={styles.turn}>
            <span className={styles.role}>You</span>
            <p className={styles.question}>{question}</p>
          </div>

          <div className={styles.turn}>
            <span className={styles.role}>Tool calls</span>
            <ToolLine call={DEBIT_CALL} />
            <ToolLine call={CREDIT_CALL} />
          </div>

          <div className={styles.turn}>
            <span className={styles.role}>Answer</span>
            <p className={styles.answer}>
              <span className={styles.figure}>
                {debit.sum} {currency}
              </span>{" "}
              went out on one debit: record <code className={styles.cite}>{debit.ids[0]}</code> in{" "}
              <code className={styles.cite}>{file}</code> ({debit.date}, {debit.description}).{" "}
              <span className={styles.figure}>
                {credit.sum} {currency}
              </span>{" "}
              came in on one credit: record <code className={styles.cite}>{credit.ids[0]}</code> in{" "}
              <code className={styles.cite}>{file}</code> ({credit.date}, {credit.description}). Both totals are
              computed in code over {batchId}, the released statement.
            </p>
          </div>
        </div>
      </ReconPanel>
    </Section>
  );
}
