"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { FlaskConical } from "lucide-react";
import type { Sample } from "../../lib/types";

type SamplesMenuProps = {
  samples: Sample[];
  disabled: boolean;
  onAddSample: (s: Sample) => void;
};

export function SamplesMenu({ samples, disabled, onAddSample }: SamplesMenuProps) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const itemsRef = useRef<(HTMLButtonElement | null)[]>([]);
  const menuId = `${useId()}-samples`;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent) {
        if (e.key !== "Escape") return;
        setOpen(false);
        buttonRef.current?.focus();
        return;
      }
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  useEffect(() => {
    if (open) itemsRef.current[active]?.focus();
  }, [open, active]);

  const count = samples.length;

  const moveTo = (i: number) => {
    setActive(i);
    itemsRef.current[i]?.focus();
  };

  const onMenuKeyDown = (e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Tab") {
      setOpen(false);
      return;
    }
    if (count === 0) return;
    if (e.key === "ArrowDown") moveTo((active + 1) % count);
    else if (e.key === "ArrowUp") moveTo((active - 1 + count) % count);
    else if (e.key === "Home") moveTo(0);
    else if (e.key === "End") moveTo(count - 1);
    else return;
    e.preventDefault();
  };

  const onButtonKeyDown = (e: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    if (count === 0) return;
    setActive(e.key === "ArrowDown" ? 0 : count - 1);
    setOpen(true);
  };

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        ref={buttonRef}
        type="button"
        className="tool-btn"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={onButtonKeyDown}
        disabled={disabled}
      >
        <FlaskConical size={15} /> Samples
      </button>
      {open && (
        <div className="popover" id={menuId} role="menu" aria-label="Sample files" onKeyDown={onMenuKeyDown}>
          <div className="popover-head mono-label" role="presentation">Synthetic golden set · {samples.length} files</div>
          {samples.map((s, i) => (
            <button
              key={s.id}
              ref={(el) => {
                itemsRef.current[i] = el;
              }}
              type="button"
              role="menuitem"
              tabIndex={i === active ? 0 : -1}
              className="ob-sample"
              onClick={() => {
                onAddSample(s);
                setOpen(false);
                buttonRef.current?.focus();
              }}
            >
              <span>
                <span className="ob-sample-name">{s.label}</span>
                <span className="ob-sample-file">{s.filename}</span>
              </span>
              {s.expect_status === "ok" ? <span className="tag tag--ok">Releases</span> : <span className="tag tag--bad"><span className="dot" />{s.expect_code}</span>}
              <span />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
