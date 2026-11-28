"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Landmark, CreditCard, FileText, Table2, ChevronDown, type LucideIcon } from "lucide-react";
import { Reveal } from "@/components/motion/reveal";
import { INPUT_GROUPS, UNVERIFIED, type InputGroup } from "./inputs-data";
import styles from "./inputs.module.css";

const ICONS: Record<InputGroup["id"], LucideIcon> = {
  statements: Landmark,
  gateways: CreditCard,
  tax: FileText,
  workpapers: Table2,
};

const COPY: Record<InputGroup["id"], { summary: string; brief: string }> = {
  statements: {
    summary: "CSV, OFX, MT940, CAMT.053, PDF and scans",
    brief: "Opening balance plus transactions equals closing, and every running balance ties.",
  },
  gateways: {
    summary: "Stripe, Razorpay and PayPal exports",
    brief: "Gross minus fees minus tax equals net, on every settlement.",
  },
  tax: {
    summary: "Form 26AS, AIS, FIRA and Form 1099‑B",
    brief: "Printed totals must match their rows, and FIRA amounts must convert at the stated rate.",
  },
  workpapers: {
    summary: "Trial balance, or any layout as .xlsx",
    brief: "Debits must equal credits, and the printed totals must match.",
  },
};

function unverifiedLayout(name: string): boolean {
  return UNVERIFIED.some((u) => u.name === name);
}

type Align = "start" | "end";
type Side = "bottom" | "top";

function InputBox({
  group,
  open,
  onOpen,
  onClose,
}: {
  group: InputGroup;
  open: boolean;
  onOpen: (id: string) => void;
  onClose: (id: string) => void;
}) {
  const Icon = ICONS[group.id];
  const copy = COPY[group.id];
  const popId = useId();
  const itemRef = useRef<HTMLLIElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const pointerType = useRef("");
  const [align, setAlign] = useState<Align>("start");
  const [side, setSide] = useState<Side>("bottom");

  useEffect(() => () => window.clearTimeout(timer.current), []);

  // Flip the popover so it stays inside the viewport.
  useEffect(() => {
    if (!open) return;
    const item = itemRef.current;
    const pop = popRef.current;
    if (!item || !pop) return;
    const margin = 12;
    const ir = item.getBoundingClientRect();
    const w = pop.offsetWidth;
    const h = pop.offsetHeight;
    const rightIfStart = ir.left + w;
    const leftIfEnd = ir.right - w;
    setAlign(rightIfStart > window.innerWidth - margin && leftIfEnd >= margin ? "end" : "start");
    const below = window.innerHeight - ir.bottom;
    const above = ir.top;
    setSide(below < h + margin + 8 && above > below ? "top" : "bottom");
  }, [open]);

  const cancel = () => window.clearTimeout(timer.current);

  return (
    <li
      ref={itemRef}
      data-reveal-child
      className={styles.item}
      data-open={open ? "true" : "false"}
      onPointerEnter={(e) => {
        if (e.pointerType === "mouse") {
          cancel();
          onOpen(group.id);
        }
      }}
      onPointerLeave={(e) => {
        if (e.pointerType === "mouse") {
          cancel();
          timer.current = window.setTimeout(() => onClose(group.id), 140);
        }
      }}
    >
      <button
        type="button"
        className={styles.box}
        aria-expanded={open}
        aria-controls={popId}
        onPointerDown={(e) => {
          pointerType.current = e.pointerType;
        }}
        onFocus={(e) => {
          if (e.currentTarget.matches(":focus-visible")) onOpen(group.id);
        }}
        onClick={() => {
          if (pointerType.current === "touch" || pointerType.current === "pen") {
            if (open) onClose(group.id);
            else onOpen(group.id);
          } else {
            onOpen(group.id);
          }
          pointerType.current = "";
        }}
      >
        <span className={styles.head}>
          <Icon aria-hidden="true" focusable="false" size={20} strokeWidth={1.5} className={styles.icon} />
          <span className={styles.title}>{group.title}</span>
        </span>
        <span className={styles.summary}>{copy.summary}</span>
        <span className={styles.meta}>
          <span className={styles.count}>{group.inputs.length} formats</span>
          <ChevronDown aria-hidden="true" focusable="false" size={16} strokeWidth={1.5} className={styles.chev} />
        </span>
      </button>

      <div
        ref={popRef}
        id={popId}
        role="group"
        aria-label={`${group.title} details`}
        className={styles.pop}
        data-align={align}
        data-side={side}
      >
        <p className={styles.brief}>{copy.brief}</p>
        <ul className={styles.formats}>
          {group.inputs.map((name) => (
            <li key={name}>
              {name}
              {unverifiedLayout(name) ? <span className={styles.quiet}> · not yet tested on real exports</span> : null}
            </li>
          ))}
        </ul>
        <p className={styles.mono}>
          {group.layouts.join("  ")}
          <br />
          {group.extensions.join("  ")}
        </p>
        {group.note ? <p className={styles.quiet}>{group.note}</p> : null}
      </div>
    </li>
  );
}

export function InputBoxes() {
  const [openId, setOpenId] = useState<string | null>(null);
  const [js, setJs] = useState(false);

  useEffect(() => setJs(true), []);

  const close = useCallback((id: string) => setOpenId((cur) => (cur === id ? null : cur)), []);

  useEffect(() => {
    if (!openId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenId(null);
    };
    const onDown = (e: PointerEvent) => {
      if (e.target instanceof Element && !e.target.closest(`.${styles.item}`)) setOpenId(null);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
    };
  }, [openId]);

  return (
    <Reveal
      as="ul"
      y={14}
      stagger={0.08}
      className={styles.grid}
      aria-label="Accepted input formats"
      data-js={js ? "true" : undefined}
    >
      {INPUT_GROUPS.map((group) => (
        <InputBox key={group.id} group={group} open={openId === group.id} onOpen={setOpenId} onClose={close} />
      ))}
    </Reveal>
  );
}
