"use client";

import { useEffect, useId, useRef, useState } from "react";
import styles from "./dot-wordmark.module.css";

type Props = {
  word?: string;
  className?: string;
};

const FALLBACK_ASPECT = 5.4;
const DOT = 6;
const GAP = 2;
const MAX_DOTS = 12000;
const MIN_ROWS = 14;
const RADIUS = 90;
const OMEGA = 2 * Math.PI * 2; // ~2 Hz
const ZETA = 0.4;
const SPRING_K = OMEGA * OMEGA;
const SPRING_C = 2 * ZETA * OMEGA;

type Field = {
  n: number;
  hx: Float32Array;
  hy: Float32Array;
  x: Float32Array;
  y: Float32Array;
  vx: Float32Array;
  vy: Float32Array;
  r: Float32Array;
  rowStart: number[];
  pitch: number;
  w: number;
  h: number;
};

function buildField(word: string, width: number, fontFamily: string): Field | null {
  const probe = document.createElement("canvas").getContext("2d");
  if (!probe || width < 10) return null;
  const weight = 800;
  probe.font = `${weight} 100px ${fontFamily}`;
  const m = probe.measureText(word);
  const left = m.actualBoundingBoxLeft;
  const tw = left + m.actualBoundingBoxRight;
  const th = m.actualBoundingBoxAscent + m.actualBoundingBoxDescent;
  if (tw <= 0 || th <= 0) return null;

  const fontSize = (100 * width) / tw;
  const height = Math.ceil((th * fontSize) / 100);

  let pitch = Math.min(DOT + GAP, height / MIN_ROWS);
  while ((width / pitch) * (height / pitch) > MAX_DOTS) pitch *= 1.05;
  const cols = Math.max(1, Math.floor(width / pitch));
  const rows = Math.max(1, Math.floor(height / pitch));
  const cw = width / cols;
  const ch = height / rows;

  const big = document.createElement("canvas");
  big.width = Math.ceil(width);
  big.height = height;
  const bctx = big.getContext("2d");
  const small = document.createElement("canvas");
  small.width = cols;
  small.height = rows;
  const sctx = small.getContext("2d", { willReadFrequently: true });
  if (!bctx || !sctx) return null;
  bctx.font = `${weight} ${fontSize}px ${fontFamily}`;
  bctx.fillStyle = "#000";
  bctx.textBaseline = "alphabetic";
  bctx.fillText(word, left * (fontSize / 100), (m.actualBoundingBoxAscent * fontSize) / 100);
  sctx.imageSmoothingEnabled = true;
  sctx.imageSmoothingQuality = "high";
  sctx.drawImage(big, 0, 0, big.width, big.height, 0, 0, cols, rows);
  const data = sctx.getImageData(0, 0, cols, rows).data;

  const cap = cols * rows;
  const hx = new Float32Array(cap);
  const hy = new Float32Array(cap);
  const r = new Float32Array(cap);
  const rowStart: number[] = [];
  const maxR = (Math.min(cw, ch) * DOT) / (DOT + GAP) / 2 + 0.4;
  let n = 0;
  for (let j = 0; j < rows; j++) {
    rowStart.push(n);
    for (let i = 0; i < cols; i++) {
      const cov = ((data[(j * cols + i) * 4 + 3] as number) ?? 0) / 255;
      if (cov < 0.1) continue;
      hx[n] = (i + 0.5) * cw;
      hy[n] = (j + 0.5) * ch;
      r[n] = maxR * Math.sqrt(cov);
      n++;
    }
  }
  rowStart.push(n);
  return {
    n,
    hx,
    hy,
    x: hx.slice(),
    y: hy.slice(),
    vx: new Float32Array(cap),
    vy: new Float32Array(cap),
    r,
    rowStart,
    pitch,
    w: width,
    h: height,
  };
}

export function DotWordmark({ word = "OpenBooks", className }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const patId = useId().replace(/:/g, "");
  const [aspect, setAspect] = useState(FALLBACK_ASPECT);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const wrap = wrapRef.current;
    const canvas = canvasRef.current;
    if (!wrap || !canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const schemeMq = window.matchMedia("(prefers-color-scheme: dark)");
    let reduced = reduceMq.matches;
    let field: Field | null = null;
    let color = "currentColor";
    let dpr = 1;
    let visible = true;
    let raf = 0;
    let last = 0;
    let disposed = false;
    // pointer in canvas-local CSS px
    let px = -1e4;
    let py = -1e4;
    let pvx = 0;
    let pvy = 0;
    let pActive = false;
    let lastMove = 0;

    const readColor = () => {
      const v = getComputedStyle(canvas).getPropertyValue("--accent").trim();
      color = v || getComputedStyle(canvas).color || "currentColor";
    };

    const draw = () => {
      if (!field) return;
      const f = field;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, f.w, f.h);
      ctx.fillStyle = color;
      for (let j = 0; j < f.rowStart.length - 1; j++) {
        const a = f.rowStart[j] ?? 0;
        const b = f.rowStart[j + 1] ?? 0;
        if (a === b) continue;
        ctx.globalAlpha = 1 - 0.4 * (j / Math.max(1, f.rowStart.length - 2));
        ctx.beginPath();
        for (let i = a; i < b; i++) {
          let rad = f.r[i] as number;
          if (reduced && pActive) {
            const dx = (f.hx[i] as number) - px;
            const dy = (f.hy[i] as number) - py;
            if (dx * dx + dy * dy < RADIUS * RADIUS * 0.25) rad *= 0.45;
          }
          const x = (reduced ? f.hx[i] : f.x[i]) as number;
          const y = (reduced ? f.hy[i] : f.y[i]) as number;
          ctx.moveTo(x + rad, y);
          ctx.arc(x, y, rad, 0, Math.PI * 2);
        }
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    };

    const step = (dt: number) => {
      const f = field;
      if (!f) return true;
      const R2 = RADIUS * RADIUS;
      const speed = Math.hypot(pvx, pvy);
      const swirl = Math.min(1, speed / 1200);
      let rest = true;
      const { hx, hy, x, y, vx, vy } = f;
      for (let i = 0; i < f.n; i++) {
        const cx = x[i] as number;
        const cy = y[i] as number;
        let cvx = vx[i] as number;
        let cvy = vy[i] as number;
        const ox = (hx[i] as number) - cx;
        const oy = (hy[i] as number) - cy;
        let ax = ox * SPRING_K - cvx * SPRING_C;
        let ay = oy * SPRING_K - cvy * SPRING_C;
        if (pActive) {
          const dx = cx - px;
          const dy = cy - py;
          const d2 = dx * dx + dy * dy;
          if (d2 < R2 && d2 > 0.01) {
            const d = Math.sqrt(d2);
            const t = 1 - d / RADIUS;
            const push = t * t * 9000;
            const nx = dx / d;
            const ny = dy / d;
            ax += nx * push;
            ay += ny * push;
            const sw = t * swirl * 5000;
            ax += -ny * sw;
            ay += nx * sw;
          }
        }
        cvx += ax * dt;
        cvy += ay * dt;
        vx[i] = cvx;
        vy[i] = cvy;
        x[i] = cx + cvx * dt;
        y[i] = cy + cvy * dt;
        if (rest && (Math.abs(ox) > 0.04 || Math.abs(oy) > 0.04 || Math.abs(cvx) > 0.1 || Math.abs(cvy) > 0.1)) {
          rest = false;
        }
      }
      return rest;
    };

    const frame = (t: number) => {
      raf = 0;
      if (disposed || !visible) return;
      const dt = Math.min(1 / 30, last ? (t - last) / 1000 : 1 / 60);
      last = t;
      // decay pointer velocity so swirl stops when the pointer stops
      if (t - lastMove > 60) {
        pvx = 0;
        pvy = 0;
      }
      const rest = step(dt);
      draw();
      if (!rest || pActive) schedule();
      else last = 0;
    };

    const schedule = () => {
      if (!raf && !disposed && visible && !reduced) raf = requestAnimationFrame(frame);
    };

    const layout = async () => {
      const width = wrap.clientWidth;
      if (width < 10) return;
      const family = getComputedStyle(canvas).fontFamily || "system-ui, sans-serif";
      try {
        await document.fonts.load(`800 100px ${family}`);
        await document.fonts.ready;
      } catch {
        /* fall through with whatever font is available */
      }
      if (disposed) return;
      const f = buildField(word, width, family);
      if (!f) return;
      field = f;
      dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.ceil(f.w * dpr);
      canvas.height = Math.ceil(f.h * dpr);
      setAspect(f.w / f.h);
      readColor();
      draw();
      setReady(true);
    };

    let lastWidth = 0;
    const ro = new ResizeObserver(() => {
      const w = wrap.clientWidth;
      if (Math.abs(w - lastWidth) < 1) return;
      lastWidth = w;
      void layout();
    });
    ro.observe(wrap);

    const io = new IntersectionObserver(
      (entries) => {
        visible = entries[0]?.isIntersecting ?? true;
        if (visible) {
          last = 0;
          schedule();
        } else if (raf) {
          cancelAnimationFrame(raf);
          raf = 0;
        }
      },
      { rootMargin: "100px" },
    );
    io.observe(wrap);

    let prevX = 0;
    let prevY = 0;
    let prevT = 0;
    const onMove = (e: PointerEvent) => {
      if (!field) return;
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const near =
        x > -RADIUS && x < rect.width + RADIUS && y > -RADIUS && y < rect.height + RADIUS;
      const now = performance.now();
      if (near && prevT) {
        const dts = Math.max(0.008, (now - prevT) / 1000);
        pvx = (x - prevX) / dts;
        pvy = (y - prevY) / dts;
      }
      prevX = x;
      prevY = y;
      prevT = now;
      lastMove = now;
      const was = pActive;
      pActive = near;
      px = x;
      py = y;
      if (near) {
        if (reduced) draw();
        else schedule();
      } else if (was) {
        if (reduced) draw();
        else schedule();
      }
    };
    const onLeave = () => {
      if (!pActive) return;
      pActive = false;
      pvx = 0;
      pvy = 0;
      if (reduced) draw();
      else schedule();
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    document.documentElement.addEventListener("pointerleave", onLeave);

    const onTheme = () => {
      readColor();
      draw();
    };
    const mo = new MutationObserver(onTheme);
    mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
    schemeMq.addEventListener("change", onTheme);
    const onReduce = () => {
      reduced = reduceMq.matches;
      draw();
      if (!reduced) schedule();
    };
    reduceMq.addEventListener("change", onReduce);

    return () => {
      disposed = true;
      if (raf) cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      mo.disconnect();
      window.removeEventListener("pointermove", onMove);
      document.documentElement.removeEventListener("pointerleave", onLeave);
      schemeMq.removeEventListener("change", onTheme);
      reduceMq.removeEventListener("change", onReduce);
    };
  }, [word]);

  return (
    <div
      ref={wrapRef}
      className={`${styles.wrap} ${className ?? ""}`}
      style={{ aspectRatio: String(aspect) }}
    >
      <span className={styles.srOnly}>{word}</span>
      <svg
        className={`${styles.fallback} ${ready ? styles.hidden : ""}`}
        viewBox={`0 0 ${FALLBACK_ASPECT * 100} 100`}
        preserveAspectRatio="none"
        aria-hidden="true"
        focusable="false"
      >
        <defs>
          <pattern id={patId} width="8" height="8" patternUnits="userSpaceOnUse">
            <circle cx="4" cy="4" r="2.6" fill="currentColor" />
          </pattern>
        </defs>
        <text
          x="0"
          y="82"
          textLength={FALLBACK_ASPECT * 100}
          lengthAdjust="spacingAndGlyphs"
          fontSize="104"
          fontWeight="800"
          fill={`url(#${patId})`}
        >
          {word}
        </text>
      </svg>
      <canvas
        ref={canvasRef}
        className={`${styles.canvas} ${ready ? styles.shown : ""}`}
        aria-hidden="true"
      />
    </div>
  );
}
