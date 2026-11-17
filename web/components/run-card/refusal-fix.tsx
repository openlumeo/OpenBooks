"use client";

import { useId, useState } from "react";
import { RotateCw } from "lucide-react";
import type { FixField } from "@/lib/stages";
import type { RunParams } from "@/lib/types";

const AMOUNT = /^-?\d+(\.\d+)?$/;
const CURRENCY = /^[A-Za-z]{3}$/;

/** Inline fix for refusals whose message asks for an input the user can supply. */
export function RefusalFix({
  fields,
  available,
  disabled,
  onRerun,
}: {
  fields: FixField[];
  available: boolean;
  disabled: boolean;
  onRerun: (p: RunParams) => void;
}) {
  const [opening, setOpening] = useState("");
  const [currency, setCurrency] = useState("");
  const [touched, setTouched] = useState(false);
  const uid = useId();

  const openingOk = !fields.includes("opening") || AMOUNT.test(opening.replace(/,/g, "").trim());
  const currencyOk = !fields.includes("currency") || CURRENCY.test(currency.trim());

  if (!available) {
    return (
      <p className="fix-note">
        To re-run with {fields.join(" and ")}, attach the file again. Files are kept only for this browser tab, not in history.
      </p>
    );
  }

  return (
    <form
      className="fix"
      onSubmit={(e) => {
        e.preventDefault();
        setTouched(true);
        if (!openingOk || !currencyOk) return;
        const p: RunParams = {};
        if (fields.includes("opening")) p.opening = opening.replace(/,/g, "").trim();
        if (fields.includes("currency")) p.currency = currency.trim().toUpperCase();
        onRerun(p);
      }}
    >
      <p className="fix-note">The engine named what it needs. Supply it and re-run this file:</p>
      {fields.includes("opening") && (
        <div className="fix-field">
          <label className="mono-label" htmlFor={`${uid}-opening`}>Opening balance</label>
          <input
            id={`${uid}-opening`}
            className="field num"
            inputMode="decimal"
            placeholder="1000.00"
            value={opening}
            onChange={(e) => setOpening(e.target.value)}
            aria-invalid={touched && !openingOk}
            aria-describedby={touched && !openingOk ? `${uid}-opening-err` : undefined}
          />
          {touched && !openingOk && <span id={`${uid}-opening-err`} className="field-error"><span className="dot" />A plain number, like 1000.00</span>}
        </div>
      )}
      {fields.includes("currency") && (
        <div className="fix-field">
          <label className="mono-label" htmlFor={`${uid}-currency`}>Currency</label>
          <input
            id={`${uid}-currency`}
            className="field num"
            placeholder="INR"
            maxLength={3}
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            aria-invalid={touched && !currencyOk}
            aria-describedby={touched && !currencyOk ? `${uid}-currency-err` : undefined}
          />
          {touched && !currencyOk && <span id={`${uid}-currency-err`} className="field-error"><span className="dot" />Three letters, like INR</span>}
        </div>
      )}
      <button type="submit" className="btn btn-primary-landing btn-sm" disabled={disabled}>
        <RotateCw size={14} /> Re-run file
      </button>
    </form>
  );
}
