"use client";

import { useEffect, useId, useRef, useState } from "react";
import { FlaskConical } from "lucide-react";
import type { Sample } from "../../lib/types";

type SamplesMenuProps = {
  samples: Sample[];
  disabled: boolean;
  onAddSample: (s: Sample) => void;
};

/** The "Samples" button and its popover. Closes on an outside click or Escape. */
export function SamplesMenu({ samples, disabled, onAddSample }: SamplesMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const menuId = `${useId()}-samples`;

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      const outside = !(e instanceof KeyboardEvent) && !rootRef.current?.contains(e.target as Node);
      if (outside || (e instanceof KeyboardEvent && e.key === "Escape")) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        className="tool-btn"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
        disabled={disabled}
      >
        <FlaskConical size={15} /> Samples
      </button>
      {open && (
        <div className="popover" id={menuId} role="menu" aria-label="Sample files">
          <div className="popover-head mono-label">Synthetic golden set · {samples.length} files</div>
          {samples.map((s) => (
            <button
              key={s.id}
              type="button"
              role="menuitem"
              className="ob-sample"
              onClick={() => {
                onAddSample(s);
                setOpen(false);
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
