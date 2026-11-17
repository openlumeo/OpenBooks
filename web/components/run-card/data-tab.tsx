import { batchSummary, columnsFor, KIND_LABEL } from "@/lib/ledger";
import type { ReleasedDoc } from "@/lib/types";

export function DataTab({ doc, onPick }: { doc: ReleasedDoc; onPick: (recordId: string) => void }) {
  const { batches, transactions, accounts } = doc.data;
  return (
    <div className="panel">
      {batches.map((b) => {
        const rows = transactions.filter((t) => t.batch_id === b.id);
        const cols = columnsFor(b.kind, rows);
        const acct = accounts.find((a) => a.id === b.account_id);
        return (
          <section key={b.id} className="panel" aria-label={`${KIND_LABEL[b.kind] ?? b.kind} ${b.id}`}>
            <div className="batch-title">
              <h3>{KIND_LABEL[b.kind] ?? b.kind}</h3>
              <span className="mono-label">{b.id} · {b.currency}{acct?.number ? ` · acct ${acct.number}` : ""} · {rows.length} row{rows.length === 1 ? "" : "s"}</span>
            </div>
            {batchSummary(b).length > 0 && (
              <dl className="summary">
                {batchSummary(b).map((s) => (
                  <div className="summary-item" key={s.key}>
                    <dt className="mono-label">{s.label}</dt>
                    <dd className="summary-value">{s.value}</dd>
                    {s.note && <dd className="summary-note">{s.note}</dd>}
                  </div>
                ))}
              </dl>
            )}
            <div className="ledger-wrap" tabIndex={0} aria-label={`${rows.length} transactions; select a row to see its evidence`}>
              <table className="ledger">
                <thead>
                  <tr>
                    <th scope="col">Id</th>
                    {cols.map((c) => (
                      <th key={c.key} scope="col" className={c.numeric ? "n" : undefined}>{c.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((t) => (
                    <tr
                      key={t.id}
                      tabIndex={0}
                      onClick={() => onPick(t.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onPick(t.id);
                        }
                      }}
                      aria-label={`${t.id}: show evidence`}
                    >
                      <td className="d">{t.id.replace("txn-", "")}</td>
                      {cols.map((c) => (
                        <td key={c.key} className={c.numeric ? "n" : c.key === "date" ? "d" : "t"}>{c.get(t)}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
