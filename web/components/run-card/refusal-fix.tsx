"use client";

import { useId, useState } from "react";
import { Paperclip, RotateCw } from "lucide-react";
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
  onAttach,
}: {
  fields: FixField[];
  available: boolean;
  disabled: boolean;
  onRerun: (p: RunParams) => void;
  onAttach: () => void;
}) {
  const [opening, setOpening] = useState("");
  const [currency, setCurrency] = useState("");
  const [order, setOrder] = useState<"" | "dmy" | "mdy">("");
  const [touched, setTouched] = useState(false);
  const uid = useId();

  const openingOk = !fields.includes("opening") || AMOUNT.test(opening.replace(/,/g, "").trim());
  const currencyOk = !fields.includes("currency") || CURRENCY.test(currency.trim());
  const orderOk = !fields.includes("date_order") || order !== "";

  if (!available) {
    const names = fields.map((f) => (f === "date_order" ? "a date order" : f === "opening" ? "an opening balance" : "a currency"));
    return (
      <div className="interrupted-recovery">
        <p className="fix-note">Attach the original file again and set {names.join(" and ")} in Params.</p>
        <button type="button" className="btn btn-ghost btn-xs" disabled={disabled} onClick={onAttach}>
          <Paperclip size={14} /> Attach original file
        </button>
      </div>
    );
  }

  return (
    <form
      className="fix"
      onSubmit={(e) => {
        e.preventDefault();
        setTouched(true);
        if (disabled || !openingOk || !currencyOk || !orderOk) return;
        const p: RunParams = {};
        if (fields.includes("opening")) p.opening = opening.replace(/,/g, "").trim();
        if (fields.includes("currency")) p.currency = currency.trim().toUpperCase();
        if (fields.includes("date_order") && order) p.date_order = order;
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
      {fields.includes("date_order") && (
        <div className="fix-field" style={{ flexBasis: 260 }}>
          <label className="mono-label" htmlFor={`${uid}-order`}>Date order</label>
          <select
            id={`${uid}-order`}
            className="field"
            value={order}
            onChange={(e) => setOrder(e.target.value as "" | "dmy" | "mdy")}
            aria-invalid={touched && !orderOk}
            aria-describedby={`${uid}-order-help`}
          >
            <option value="">Choose…</option>
            <option value="dmy">Day first: 03/04 is 3 April</option>
            <option value="mdy">Month first: 03/04 is 4 March</option>
          </select>
          {touched && !orderOk && <span className="field-error"><span className="dot" />Pick the order the export uses</span>}
        </div>
      )}
      {fields.includes("date_order") && (
        <p id={`${uid}-order-help`} className="fix-note">
          Every date in this file has a day and month of 12 or less, so the file itself cannot prove the order. Check one date
          against the source before choosing: the wrong order moves transactions between months.
        </p>
      )}
      <button type="submit" className="btn btn-primary-landing btn-sm" disabled={disabled}>
        <RotateCw size={14} /> Re-run file
      </button>
    </form>
  );
}
