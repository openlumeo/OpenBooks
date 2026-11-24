import { useId, useMemo } from "react";
import type { ReleasedDoc } from "@/lib/types";

const METHOD_LABEL: Record<string, string> = {
  parser: "Parser (structured file)",
  pdf_text: "PDF text layer",
  ocr: "OCR",
  "pdf_text+model": "PDF text layer, model cross-checked",
  "ocr+model": "OCR, model cross-checked",
};

export function EvidenceTab({
  doc,
  record,
  onRecord,
}: {
  doc: ReleasedDoc;
  record: string;
  onRecord: (id: string) => void;
}) {
  const inputId = useId();
  const records = useMemo(() => {
    const ids = new Set<string>();
    for (const k of Object.keys(doc.evidence)) ids.add(k.slice(0, k.indexOf(".")));
    return [...ids].sort((a, b) =>
      a.startsWith("batch") === b.startsWith("batch") ? a.localeCompare(b) : a.startsWith("batch") ? -1 : 1,
    );
  }, [doc]);
  const current = records.includes(record) ? record : (records[0] ?? "");
  const fields = Object.entries(doc.evidence).filter(([k]) => k.startsWith(`${current}.`));

  return (
    <div className="panel">
      <div className="evidence-pick">
        <label htmlFor={inputId} className="mono-label">
          Record
        </label>
        <select id={inputId} className="field" value={current} onChange={(e) => onRecord(e.target.value)}>
          {records.map((r) => (
            <option key={r} value={r}>
              {r}
            </option>
          ))}
        </select>
        <span className="t-body-sm">Where every value of this record was read from.</span>
      </div>
      <div className="ledger-wrap" role="region" tabIndex={0} aria-label="Source evidence">
        <table className="kv">
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Raw text</th>
              <th scope="col">Page</th>
              <th scope="col">Row</th>
              <th scope="col">Box</th>
              <th scope="col">Method</th>
              <th scope="col">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {fields.map(([k, e]) => (
              <tr key={k}>
                <td className="n">{k.slice(current.length + 1)}</td>
                <td className="raw">{e.raw_text || "—"}</td>
                <td className="n">{e.page ?? "—"}</td>
                <td className="n">{e.row ?? "—"}</td>
                <td className="n">{e.bbox ? e.bbox.map((v) => Math.round(v * 10) / 10).join(", ") : "—"}</td>
                <td>{METHOD_LABEL[e.method] ?? e.method}</td>
                <td className="n">{e.confidence !== undefined ? e.confidence.toFixed(4) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
