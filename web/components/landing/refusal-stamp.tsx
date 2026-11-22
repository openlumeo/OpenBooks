import type { CSSProperties } from "react";
import styles from "./refusals.module.css";

const RING_DASH: CSSProperties = { strokeDasharray: "3 2.2" };

export function RefusalStamp() {
  return (
    <svg
      viewBox="0 0 48 48"
      aria-hidden="true"
      focusable="false"
      className={styles.stamp}
    >
      <circle cx="24" cy="24" r="20.5" />
      <circle cx="24" cy="24" r="16" style={RING_DASH} />
      <path d="M17 17 L31 31 M31 17 L17 31" />
    </svg>
  );
}
