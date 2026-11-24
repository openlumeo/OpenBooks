import { useMemo } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { batchSummary, columnsFor, KIND_LABEL } from "@/lib/ledger";
import type { Batch, ReleasedDoc, Transaction } from "@/lib/types";

const PAGE_SIZE = 50;

type DataTabProps = {
  doc: ReleasedDoc;
  onPick: (recordId: string) => void;
  pages: Record<string, number>;
  onPage: (batchId: string, page: number) => void;
};

export function DataTab({ doc, onPick, pages, onPage }: DataTabProps) {
  const { batches, transactions, accounts } = doc.data;
  const grouped = useMemo(() => {
    const groups = new Map<string, Transaction[]>();
    for (const transaction of transactions) {
      let rows = groups.get(transaction.batch_id);
      if (!rows) {
        rows = [];
        groups.set(transaction.batch_id, rows);
      }
      rows.push(transaction);
    }
    return groups;
  }, [transactions]);

  return (
    <div className="panel">
      {batches.map((batch) => (
        <BatchLedger
          key={batch.id}
          batch={batch}
          rows={grouped.get(batch.id) ?? []}
          account={accounts.find((a) => a.id === batch.account_id)?.number}
          page={pages[batch.id] ?? 0}
          onPage={(page) => onPage(batch.id, page)}
          onPick={onPick}
        />
      ))}
    </div>
  );
}

function BatchLedger({
  batch,
  rows,
  account,
  page,
  onPage,
  onPick,
}: {
  batch: Batch;
  rows: Transaction[];
  account?: string | null;
  page: number;
  onPage: (page: number) => void;
  onPick: (recordId: string) => void;
}) {
  const cols = useMemo(() => columnsFor(batch.kind, rows), [batch.kind, rows]);
  const summary = batchSummary(batch);
  const start = page * PAGE_SIZE;
  const end = Math.min(start + PAGE_SIZE, rows.length);
  const title = KIND_LABEL[batch.kind] ?? batch.kind;
  return (
    <section className="panel" aria-label={`${title} ${batch.id}`}>
      <div className="batch-title">
        <h3>{title}</h3>
        <span className="mono-label">
          {batch.id} · {batch.currency}
          {account ? ` · acct ${account}` : ""} · {rows.length} {rows.length === 1 ? "row" : "rows"}
        </span>
      </div>
      {summary.length > 0 && (
        <dl className="summary">
          {summary.map((s) => (
            <div className="summary-item" key={s.key}>
              <dt className="mono-label">{s.label}</dt>
              <dd className="summary-value">{s.value}</dd>
              {s.note && <dd className="summary-note">{s.note}</dd>}
            </div>
          ))}
        </dl>
      )}
      {rows.length > PAGE_SIZE && (
        <div className="ledger-pagination" aria-label={`${batch.id} transaction pages`}>
          <span className="mono-label" role="status">
            Rows {start + 1}–{end} of {rows.length}
          </span>
          <div>
            <button
              type="button"
              className="icon-btn icon-btn--boxed"
              aria-label="Previous transaction page"
              disabled={page === 0}
              onClick={() => onPage(page - 1)}
            >
              <ChevronLeft size={16} />
            </button>
            <button
              type="button"
              className="icon-btn icon-btn--boxed"
              aria-label="Next transaction page"
              disabled={end === rows.length}
              onClick={() => onPage(page + 1)}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
      {rows.length > 0 && (
        <div key={page} className="ledger-wrap" tabIndex={0} role="region" aria-label={`Transactions for ${batch.id}`}>
          <table className="ledger">
            <caption className="sr-only">{title} transactions. Select a record ID to view its evidence.</caption>
            <thead>
              <tr>
                <th scope="col">Record ID</th>
                {cols.map((c) => (
                  <th key={c.key} scope="col" className={c.numeric ? "n" : undefined}>
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(start, end).map((t) => (
                <tr key={t.id}>
                  <th scope="row" className="ledger-record">
                    <button
                      type="button"
                      className="copy-inline"
                      onClick={() => onPick(t.id)}
                      aria-label={`Show evidence for ${t.id}`}
                    >
                      {t.id}
                    </button>
                  </th>
                  {cols.map((c) => (
                    <td key={c.key} className={c.numeric ? "n" : c.key === "date" ? "d" : "t"}>
                      {c.get(t)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
