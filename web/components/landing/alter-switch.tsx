'use client';

import styles from './alter-switch.module.css';

export type AlterSwitchProps = {
  checked: boolean;
  onChange: (next: boolean) => void;
  className?: string;
};

export function AlterSwitch({ checked, onChange, className }: AlterSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      className={[styles.switch, className].filter(Boolean).join(' ')}
      onClick={() => onChange(!checked)}
    >
      <span aria-hidden="true" className={styles.track}>
        <span className={styles.thumb} />
      </span>
      <span className={styles.label}>ALTER ONE BALANCE</span>
      <span aria-hidden="true" className={styles.state}>
        {checked ? 'ON' : 'OFF'}
      </span>
    </button>
  );
}
