"use client";

// Paper stack: an industrial 3D element made of translucent ledger sheets.
// Content is real engine output from proof-data.ts (strings as-is, never Number()).
//
// Static first: the sheets are rendered in their fanned end state through inline
// custom properties, so no-JS and reduced-motion visitors see the final composition.
// GSAP runs only inside gsap.matchMedia for prefers-reduced-motion: no-preference:
//   (a) scroll-scrubbed separation: sheets fan from flat to their CSS offsets as the
//       section crosses the viewport (ScrollTrigger scrub 0.6, ease none).
//   (b) pointer tilt on the stack via gsap.quickTo, max 6 degrees, fine pointers only.
// No ambient looping motion. will-change is set only while the scene is in view.
import { useEffect, useRef } from "react";
import type { CSSProperties } from "react";
import { RELEASED, TAMPERED, type LedgerLine } from "./proof-data";
import { Sketch } from "@/components/motion/sketch";
import { gsap, DESKTOP_MOTION, markMotionReady } from "@/components/motion/gsap-setup";
import styles from "./paper-stack.module.css";

const MAX_TILT_DEG = 6;
const VISIBLE_SHEETS = 4;

type SheetRow = LedgerLine & { state: "matched" | "unmatched" };

type SheetSpec = {
  /** 0 is the top sheet. Also the DOM-independent stacking index. */
  index: number;
  title: string;
  meta: string;
  metaTone?: "error";
  rows: readonly SheetRow[];
  /** Top sheet only: the equation line and the optional stamp. */
  equation?: boolean;
  footnote?: string;
  /** Background alpha of the sheet fill (translucent surfaces). */
  fill: number;
  /** Fanned offsets in px (y, z) and deg (rx, ry), before the --depth multiplier. */
  y: number;
  z: number;
  rx: number;
  ry: number;
};

const RELEASED_ROWS: readonly SheetRow[] = RELEASED.rows.map((row) => ({ ...row, state: "matched" }));

const TAMPERED_ROWS: readonly SheetRow[] = TAMPERED.rows.map((row) => ({
  ...row,
  state: row.id === TAMPERED.offendingRowId ? "unmatched" : "matched",
}));

// Index 0 is the top sheet. Lower sheets drop down and back, so their bottom
// ledger rows peek out beneath the sheet above. The tampered twin is on index 2
// and its last row (the offending one) is the bottom row of that sheet.
const SHEETS: readonly SheetSpec[] = [
  {
    index: 0,
    title: RELEASED.fileName,
    meta: `${RELEASED.currency} · ${RELEASED.periodStart} to ${RELEASED.periodEnd}`,
    rows: RELEASED_ROWS,
    equation: true,
    footnote: `${RELEASED.hiddenRowCount} of ${RELEASED.transactionCount} rows not shown`,
    fill: 0.94,
    y: 0,
    z: 48,
    rx: 0,
    ry: 0,
  },
  {
    index: 1,
    title: `${RELEASED.fileName} · ledger`,
    meta: "running balance",
    rows: RELEASED_ROWS.slice(0, 4),
    fill: 0.86,
    y: 46,
    z: 22,
    rx: 0,
    ry: -0.5,
  },
  {
    index: 2,
    title: TAMPERED.fileName,
    meta: TAMPERED.code,
    metaTone: "error",
    rows: TAMPERED_ROWS.slice(1),
    fill: 0.78,
    y: 92,
    z: -4,
    rx: 0,
    ry: 1,
  },
  {
    index: 3,
    title: `${RELEASED.fileName} · copy`,
    meta: "matched",
    rows: RELEASED_ROWS.slice(1),
    fill: 0.7,
    y: 138,
    z: -30,
    rx: 0,
    ry: -1.5,
  },
  {
    index: 4,
    title: "ledger · archived",
    meta: "matched",
    rows: RELEASED_ROWS.slice(2),
    fill: 0.62,
    y: 184,
    z: -56,
    rx: 0,
    ry: 2,
  },
  {
    index: 5,
    title: "workpaper",
    meta: `${RELEASED.transactionCount} rows`,
    rows: RELEASED_ROWS.slice(3),
    fill: 0.54,
    y: 230,
    z: -82,
    rx: 0,
    ry: -2.5,
  },
];

function Equation() {
  return (
    <div className={styles.equation}>
      <span>
        Opening <b>{RELEASED.opening}</b>
      </span>
      <span>
        + CR <b>{RELEASED.creditTotal}</b>
      </span>
      <span>
        - DR <b>{RELEASED.debitTotal}</b>
      </span>
      <span>
        = Closing <b>{RELEASED.closing}</b>
      </span>
    </div>
  );
}

function Sheet({ spec, stamp }: { spec: SheetSpec; stamp: boolean }) {
  const stamped = stamp && spec.index === 0;
  const style = {
    "--fill": String(spec.fill),
    "--y": `${spec.y}px`,
    "--z": `${spec.z}px`,
    "--rx": `${spec.rx}deg`,
    "--ry": `${spec.ry}deg`,
  } as unknown as CSSProperties;

  return (
    <div
      data-sheet=""
      data-index={spec.index}
      data-level={spec.index}
      data-stamped={stamped ? "true" : "false"}
      className={`${styles.sheet} lp-paper`}
      style={style}
    >
      <div className={styles.head}>
        <span>{spec.title}</span>
        <span className={styles.meta} data-tone={spec.metaTone}>
          {spec.meta}
        </span>
      </div>
      {spec.equation ? <Equation /> : null}
      {stamped ? <span className={styles.stamp}>RELEASED</span> : null}
      <ul className={styles.rows}>
        {spec.rows.map((row) => (
          <li key={`${spec.index}-${row.id}`} className={styles.row} data-state={row.state}>
            <span>{row.date}</span>
            <span className={styles.desc}>{row.description}</span>
            <span>{row.direction}</span>
            <span className={styles.num}>{row.amount}</span>
            <span className={styles.num}>{row.balance}</span>
            {row.state === "matched" && spec.index === 0 ? (
              <Sketch kind="tick" tone="mint" className={styles.tick} />
            ) : null}
            {row.state === "unmatched" ? (
              <Sketch kind="scribble" tone="rose" className={styles.tamper} />
            ) : null}
          </li>
        ))}
      </ul>
      {spec.footnote ? <p className={styles.foot}>{spec.footnote}</p> : null}
    </div>
  );
}

export type PaperStackProps = {
  className?: string;
  /** Shows the lavender RELEASED stamp on the top sheet. Default false (one-lavender rule is the page's choice). */
  stamp?: boolean;
  /** Enables pointer tilt on fine pointers when motion is allowed. Default true. */
  interactive?: boolean;
};

const clamp = (value: number) => Math.max(-1, Math.min(1, value));

/** Scrubs sheets from their start pose to the fanned CSS pose as the scene scrolls in. */
function scrubSheets(
  sheets: HTMLElement[],
  scene: HTMLElement,
  depth: number,
  desktop: boolean,
  setWillChange: (value: string) => void,
) {
  const fanned =
    (pick: (spec: SheetSpec) => number) =>
    (_index: number, target: HTMLElement) => {
      const spec = SHEETS.find((s) => s.index === Number(target.dataset.index));
      return spec ? pick(spec) * depth : 0;
    };
  // Desktop: sheets start tipped back and recessed, lying on the desk.
  const from = desktop
    ? {
        y: 0,
        z: (i: number) => -60 - i * 40,
        rotationX: (i: number) => 24 + i * 6,
        rotationY: 0,
        opacity: 0.6,
      }
    : { y: 0, z: 0, rotationX: 0, rotationY: 0 };

  gsap.fromTo(
    sheets,
    from,
    {
      y: fanned((spec) => spec.y),
      z: fanned((spec) => spec.z),
      rotationX: fanned((spec) => spec.rx),
      rotationY: fanned((spec) => spec.ry),
      opacity: 1,
      ease: "none",
      scrollTrigger: {
        trigger: scene,
        start: "top bottom",
        end: "top 30%",
        scrub: 0.6,
        onToggle: (self) => setWillChange(self.isActive ? "transform" : ""),
      },
    },
  );
}

/** Attaches the pointer tilt to the scene and returns the function that removes it. */
function attachPointerTilt(scene: HTMLElement, stack: HTMLElement): () => void {
  const setRotationX = gsap.quickTo(stack, "rotationX", {
    duration: 0.9,
    ease: "elastic.out(1, 0.5)",
  });
  const setRotationY = gsap.quickTo(stack, "rotationY", {
    duration: 0.9,
    ease: "elastic.out(1, 0.5)",
  });

  const onMove = (event: PointerEvent) => {
    const rect = scene.getBoundingClientRect();
    if (rect.width === 0 || rect.height === 0) return;
    const nx = clamp(((event.clientX - rect.left) / rect.width) * 2 - 1);
    const ny = clamp(((event.clientY - rect.top) / rect.height) * 2 - 1);
    setRotationY(nx * MAX_TILT_DEG);
    setRotationX(-ny * MAX_TILT_DEG);
  };
  const onLeave = () => {
    setRotationX(0);
    setRotationY(0);
  };

  scene.addEventListener("pointermove", onMove);
  scene.addEventListener("pointerleave", onLeave);
  return () => {
    scene.removeEventListener("pointermove", onMove);
    scene.removeEventListener("pointerleave", onLeave);
  };
}

export function PaperStack({ className, stamp = false, interactive = true }: PaperStackProps) {
  const sceneRef = useRef<HTMLDivElement>(null);
  const stackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const scene = sceneRef.current;
    const stack = stackRef.current;
    if (!scene || !stack) return;

    markMotionReady();
    const sheets = Array.from(stack.querySelectorAll<HTMLElement>("[data-sheet]"));
    const mm = gsap.matchMedia();

    // Conditions re-run the block when the viewport crosses the breakpoint, so the
    // depth read below always matches the CSS --depth in effect.
    mm.add(
      {
        motion: "(prefers-reduced-motion: no-preference)",
        desktop: DESKTOP_MOTION,
        narrow: "(max-width: 639px)",
        wide: "(min-width: 640px)",
      },
      (ctx) => {
        const conditions = (ctx as unknown as { conditions?: Record<string, boolean> }).conditions ?? {};
        if (!conditions.motion) return undefined;

        const parsedDepth = Number.parseFloat(getComputedStyle(scene).getPropertyValue("--depth"));
        const depth = Number.isFinite(parsedDepth) ? parsedDepth : 1;

        const setWillChange = (value: string) => {
          stack.style.willChange = value;
          for (const el of sheets) el.style.willChange = value;
        };

        // (a) Scroll-scrubbed separation.
        scrubSheets(sheets, scene, depth, Boolean(conditions.desktop), setWillChange);

        // (b) Pointer tilt on the stack. Fine pointers only, and only when the
        // stack is wide enough for depth to matter.
        const fine = window.matchMedia("(pointer: fine)").matches;
        // matchMedia calls a returned function when the query stops matching or on revert.
        if (interactive && conditions.wide && fine) {
          return attachPointerTilt(scene, stack);
        }
        return undefined;
      },
    );

    return () => {
      mm.revert();
      stack.style.willChange = "";
      for (const el of sheets) el.style.willChange = "";
    };
  }, [interactive]);

  return (
    <div className={[styles.root, className].filter(Boolean).join(" ")}>
      <p className={styles.srOnly}>A stack of ledger sheets: one proven statement and one refused twin.</p>
      <div aria-hidden="true" ref={sceneRef} className={styles.scene}>
        <div className={styles.contact} />
        <div ref={stackRef} className={styles.stack}>
          {/* Rendered back to front, so the DOM order matches the stacking order even without 3D. */}
          {[...SHEETS.slice(0, VISIBLE_SHEETS)].reverse().map((spec) => (
            <Sheet key={spec.index} spec={spec} stamp={stamp} />
          ))}
        </div>
      </div>
    </div>
  );
}
