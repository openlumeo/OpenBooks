import styles from "./refusals.module.css";

export function RefusalStamp() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false" className={styles.stamp}>
      <path d="M14 14 L34 34 M34 14 L14 34" />
    </svg>
  );
}
