// Generic hardware frame drawn in CSS. Server-safe, static (no motion), renders without JS.
// The outer hardware is rounded; everything inside the screen is square (DESIGN.md radius rule).
import type { ReactNode } from "react";
import styles from "./device-frame.module.css";

export type DeviceFrameProps = {
  children?: ReactNode;
  /** Visible caption under the device. */
  label?: string;
  variant?: "laptop" | "phone";
};

export function DeviceFrame({ children, label, variant = "laptop" }: DeviceFrameProps) {
  const phone = variant === "phone";
  return (
    <figure className={[styles.frame, phone ? styles.phone : styles.laptop].join(" ")}>
      <div className={styles.body}>
        <div className={styles.lid}>
          <span className={styles.camera} aria-hidden="true" />
          <div className={styles.screen}>
            <div className={styles.content}>{children}</div>
            <span className={styles.glare} aria-hidden="true" />
          </div>
        </div>
        {phone ? null : (
          <div className={styles.base} aria-hidden="true">
            <span className={styles.lip} />
          </div>
        )}
        <span className={styles.shadow} aria-hidden="true" />
      </div>
      {label ? <figcaption className={styles.label}>{label}</figcaption> : null}
    </figure>
  );
}
