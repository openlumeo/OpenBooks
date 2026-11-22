"use client";

import { Fragment, type JSX } from "react";
import { DigitRoll } from "./digit-roll";
import { ENGINE_STAGES, RELEASED, TAMPERED } from "./proof-data";
import styles from "./hero-monolith.module.css";

function rowOf<T extends { id: string }>(rows: readonly T[], id: string): T {
  const row = rows.find((r) => r.id === id);
  if (!row) throw new Error(`proof-data: missing ledger row ${id}`);
  return row;
}

const TXN4_RELEASED_BALANCE = rowOf(RELEASED.rows, "txn-00005").balance;

const RELEASED_EQUATION = `${RELEASED.opening} + ${RELEASED.creditTotal} − ${RELEASED.debitTotal} = ${RELEASED.closing}`;
const REFUSED_EQUATION = `${rowOf(TAMPERED.rows, "txn-00004").balance} − ${rowOf(TAMPERED.rows, "txn-00005").amount} = ${TAMPERED.offendingComputedBalance} ≠ ${TAMPERED.offendingPrintedBalance}`;
const RELEASED_LABEL = `Released statement, statement.csv, INR. Opening ${RELEASED.opening}. Five transactions shown, then closing ${RELEASED.closing}. Equation: ${RELEASED.opening} plus ${RELEASED.creditTotal} minus ${RELEASED.debitTotal} equals ${RELEASED.closing}. Balance stage passed on every row.`;
const REFUSED_LABEL = `Refused statement, statement.csv, INR. Balance check failed at TXN 4: printed balance ${TAMPERED.offendingPrintedBalance}, running balance ${TAMPERED.offendingComputedBalance}. Refusal code ${TAMPERED.code}: ${TAMPERED.message}`;

export function HeroMonolith({ state }: { state: "released" | "refused" }): JSX.Element {
  const refused = state === "refused";
  const txn4Balance = refused ? TAMPERED.offendingPrintedBalance : TXN4_RELEASED_BALANCE;
  const stageCount = ENGINE_STAGES.length;

  return (
    <div className={styles.scene} data-hero-scene data-state={state}>
      <div className={styles.back} data-hero-plane="back" aria-hidden="true" />

      <div className={styles.tilt} data-hero-plane="instrument">
        <figure className={`${styles.instrument} lp-paper`} aria-label={refused ? REFUSED_LABEL : RELEASED_LABEL}>
          <ol className={styles.rail} aria-label="Engine stages">
            {ENGINE_STAGES.map((stage, i) => {
              const isBalance = i === stageCount - 1;
              return (
                <Fragment key={stage}>
                  {i > 0 ? <li className={styles.link} aria-hidden="true" /> : null}
                  <li className={styles.stage} data-hero-node={isBalance ? "balance" : undefined}>
                    <i className={styles.node} aria-hidden="true" />
                    <span>{stage}</span>
                    {isBalance ? (
                      <span className={styles.tagSlot}>
                        <span className={styles.tagPass} aria-hidden={refused}>Pass</span>
                        <span className={styles.tagFail} aria-hidden={!refused}>Fail</span>
                      </span>
                    ) : null}
                  </li>
                </Fragment>
              );
            })}
            <li className={styles.tail} data-hero-rail-tail aria-hidden="true" />
          </ol>

          <div className={styles.head}>
            <span>statement.csv &middot; INR</span>
            <span className={styles.slot}>
              <span className={styles.stamp} data-hero-stamp aria-hidden={refused}>Released</span>
              <span className={styles.plate} data-hero-verdict aria-hidden={!refused}>
                Refused &middot; BALANCE_MISMATCH
              </span>
            </span>
          </div>

          <div className={styles.ledger}>
            <div className={styles.colHead} aria-hidden="true">
              <span className={styles.date}>Date</span>
              <span>Description</span>
              <span className={styles.dir}>Dir</span>
              <span className={styles.num}>Amount</span>
              <span className={styles.num}>Balance</span>
            </div>

            <div className={`${styles.row} ${styles.sum}`} data-hero-row="opening">
              <span className={styles.tie} data-hero-tie aria-hidden="true" />
              <span className={styles.sumLabel}>Opening balance</span>
              <span className={styles.num}>{RELEASED.opening}</span>
            </div>

            {RELEASED.rows.map((row, i) => {
              const isBreak = i === 4;
              return (
                <div className={styles.row} data-hero-row={`txn-${i}`} key={row.id}>
                  <span className={styles.tie} data-hero-tie aria-hidden="true" />
                  <span className={styles.date}>{row.date}</span>
                  <span>{row.description}</span>
                  <span className={styles.dir}>{row.direction}</span>
                  <span className={styles.num}>{row.amount}</span>
                  <span className={styles.num}>
                    {isBreak ? <DigitRoll value={txn4Balance} /> : row.balance}
                  </span>
                </div>
              );
            })}

            <div className={styles.gap} aria-hidden="true">&hellip;</div>

            <div className={`${styles.row} ${styles.sum} ${styles.close}`} data-hero-row="closing">
              <span className={styles.tie} data-hero-tie aria-hidden="true" />
              <span className={styles.sumLabel}>Closing balance</span>
              <span className={styles.num}>{RELEASED.closing}</span>
            </div>
          </div>

          <div className={styles.foot}>
            <div className={styles.eqRow}>
              <span className={styles.eqLabel}>Equation</span>
              <div className={styles.eqStack}>
                <p className={styles.eqReleased} data-hero-equation="released" aria-hidden={refused}>
                  {RELEASED_EQUATION}
                </p>
                <p className={styles.eqRefused} data-hero-equation="refused" aria-hidden={!refused}>
                  {REFUSED_EQUATION}
                </p>
              </div>
            </div>
            <p className={styles.caption} aria-hidden={!refused}>
              {TAMPERED.message}
            </p>
          </div>
        </figure>
      </div>
    </div>
  );
}
