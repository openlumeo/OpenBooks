"use client";

import { useEffect, useRef, useState } from "react";
import { predictRoles } from "@/lib/engine-client";
import type { RolesDoc, RunParams } from "@/lib/types";

const percent = (value: number) => `${(value * 100).toFixed(1)}%`;

export function ModelReading({ file, params, disabled }: { file: File; params: RunParams; disabled: boolean }) {
  const [reading, setReading] = useState<RolesDoc>();
  const [error, setError] = useState<string>();
  const [loading, setLoading] = useState(false);
  const [pageIndex, setPageIndex] = useState(0);
  const request = useRef<AbortController | null>(null);

  useEffect(() => () => request.current?.abort(), []);

  async function inspect() {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setLoading(true);
    setError(undefined);
    try {
      setReading(await predictRoles(file, params, controller.signal));
    } catch (e) {
      if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Could not read this file.");
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setLoading(false);
    }
  }

  return (
    <details className="panel">
      <summary>Model reading</summary>
      <p className="t-body-sm">
        Inspect the words and roles the model read. The statement checks determine whether the file is released.
      </p>
      {!reading && (
        <button type="button" className="btn btn-ghost btn-xs" disabled={disabled || loading} onClick={inspect}>
          {error ? "Retry model reading" : "Read with model"}
        </button>
      )}
      {loading && <p role="status">Reading words and predicting roles. Scanned images can take a few minutes.</p>}
      {error && <p role="alert">{error}</p>}
      {reading && (
        <>
          <p role="status" className="checks-line">
            <span>
              {reading.method === "ocr" ? "OCR" : "PDF text"} · {reading.summary.tokens} words
            </span>
            <span>
              {reading.summary.abstained} uncertain from model ({percent(reading.summary.abstain_rate)})
            </span>
            {reading.layout && reading.layout.resolved_abstentions > 0 && (
              <span>{reading.layout.resolved_abstentions} assigned by checked layout</span>
            )}
            <span>
              {reading.summary.inference_ms} ms inference · {reading.summary.device}
            </span>
          </p>
          {reading.pages.length === 0 && <p>No readable words found.</p>}
          {reading.pages.length > 0 && (
            <>
              <label>
                Page{" "}
                <select value={pageIndex} onChange={(e) => setPageIndex(Number(e.target.value))}>
                  {reading.pages.map((page, i) => (
                    <option key={page.page} value={i}>
                      {page.page}
                    </option>
                  ))}
                </select>
              </label>
              <div style={{ maxHeight: 320, overflow: "auto" }}>
                <table style={{ width: "100%", textAlign: "left" }}>
                  <thead>
                    <tr>
                      <th>Word</th>
                      <th>Model role</th>
                      <th>Checked layout role</th>
                      <th>Value type</th>
                      <th>OCR confidence</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reading.pages[pageIndex]?.tokens.map((token, i) => (
                      <tr key={i}>
                        <td>
                          {token.text}
                          {token.ocr_text && <small> (OCR read {token.ocr_text})</small>}
                        </td>
                        <td>
                          {token.abstained
                            ? `Uncertain (${token.role_set.join(", ") || "no candidates"})`
                            : token.role_set[0]}
                        </td>
                        <td>{token.layout_role ?? "—"}</td>
                        <td>{token.type_set.join(", ") || "Uncertain"}</td>
                        <td>{token.ocr_confidence == null ? "—" : percent(token.ocr_confidence)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </details>
  );
}
