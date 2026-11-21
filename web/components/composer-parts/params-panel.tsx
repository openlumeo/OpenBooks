"use client";

import { useEffect, useState } from "react";
import type { RunParams } from "../../lib/types";
import { draftError, draftToParams, isCurrencyInvalid, isOpeningInvalid } from "./params-draft";

type ParamsPanelProps = {
  id: string;
  params: RunParams;
  setParams: (p: RunParams) => void;
  onError: (e: string | null) => void;
  modelAvailable: boolean;
  modelIssue?: string | null;
};

export function ParamsPanel({ id, params, setParams, onError, modelAvailable, modelIssue }: ParamsPanelProps) {
  const [currency, setCurrency] = useState(params.currency ?? "");
  const [opening, setOpening] = useState(params.opening ?? "");
  const [account, setAccount] = useState(params.account ?? "");
  const draft = { currency, opening, account };

  useEffect(() => {
    const error = draftError(draft);
    onError(error);
    if (error) return;
    const next = draftToParams(params, draft);
    if (JSON.stringify(next) !== JSON.stringify(params)) setParams(next);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currency, opening, account]);

  return (
    <div className="params" id={id} role="group" aria-label="Run parameters">
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-cur`}>Currency</label>
        <input id={`${id}-cur`} className="field num" placeholder="From file" maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value)} aria-invalid={isCurrencyInvalid(currency)} />
      </div>
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-open`}>Opening balance</label>
        <input id={`${id}-open`} className="field num" inputMode="decimal" placeholder="From file" value={opening} onChange={(e) => setOpening(e.target.value)} aria-invalid={isOpeningInvalid(opening)} />
      </div>
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-acct`}>Account</label>
        <input id={`${id}-acct`} className="field" placeholder="Optional label" value={account} onChange={(e) => setAccount(e.target.value)} />
      </div>
      <div className="params-field">
        <label className="mono-label" htmlFor={`${id}-order`}>Date order</label>
        <select
          id={`${id}-order`}
          className="field"
          value={params.date_order ?? ""}
          onChange={(e) => {
            const v = e.target.value as "" | "dmy" | "mdy";
            const next = { ...params };
            if (v) next.date_order = v;
            else delete next.date_order;
            setParams(next);
          }}
        >
          <option value="">Prove from file</option>
          <option value="dmy">Day first (03/04 = 3 Apr)</option>
          <option value="mdy">Month first (03/04 = 4 Mar)</option>
        </select>
      </div>
      <div className="params-toggles">
        <label className="check">
          <input type="checkbox" checked={params.ocr !== false} onChange={(e) => setParams({ ...params, ocr: e.target.checked })} />
          Read scans with OCR
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={!!params.allow_derived_opening}
            onChange={(e) => setParams({ ...params, allow_derived_opening: e.target.checked || undefined })}
          />
          Allow derived opening balance
        </label>
        <label className="check" title={modelAvailable ? undefined : `Unavailable: ${modelIssue ?? "the engine has no usable model"}`}>
          <input type="checkbox" checked={!!params.model} disabled={!modelAvailable} onChange={(e) => setParams({ ...params, model: e.target.checked || undefined })} />
          Model cross-check for PDFs and scans
        </label>
      </div>
      <p className="params-help">
        Applies to every file in this run; sample files bring their own. A derived opening never counts as independent evidence.
        Dates are read in the order the file proves (a day above 12); bank statements without proof are read day-first, and
        PayPal and 1099-B refuse rather than guess. The model cross-check can only add refusals, never a release.
      </p>
    </div>
  );
}
