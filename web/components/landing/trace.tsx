import { Reveal } from "@/components/motion/reveal";
import { Sketch, SketchAnnotation } from "@/components/motion/sketch";
import { ReconPanel, ReconRow } from "./reconciliation";
import { Section } from "./section";
import { TRACE_SAMPLE, type TraceEvidence } from "./trace-data";
import { WipeReveal } from "@/components/motion/wipe-reveal";
import { TraceLine } from "./trace-line";
import styles from "./trace.module.css";

const tx = TRACE_SAMPLE.transaction;

type TxField = {
  field: string;
  label: string;
  value: string;
  unit?: string;
};

const TX_FIELDS: readonly TxField[] = [
  { field: "date", label: "Date", value: tx.date },
  { field: "description", label: "Description", value: tx.description ?? "null" },
  { field: "direction", label: "Direction", value: tx.direction },
  { field: "amount", label: "Amount", value: tx.amount.amount, unit: tx.amount.currency },
  { field: "balance_after", label: "Balance after", value: tx.balance_after.amount, unit: tx.balance_after.currency },
];

function evidenceFor(field: string): TraceEvidence | undefined {
  return TRACE_SAMPLE.evidence.find((e) => e.key === `${tx.id}.${field}`);
}

function show(v: string | number | null | undefined): string {
  return v === null || v === undefined ? "null" : String(v);
}

export function Trace() {
  const hasConfidence = TRACE_SAMPLE.evidence.some((e) => e.confidence !== undefined);
  return (
    <Section id="trace" heading="Every figure leads back to its source.">
      <p className={`t-lede ${styles.lede}`}>
        Each value carries its page, box, row, raw text and extraction method. Review a figure the way you would review a
        voucher: by looking at the original.
      </p>
      <Reveal as="div" y={14} className={styles.reveal}>
      <WipeReveal from="top">
      <figure className={`lp-figure ${styles.figure}`} aria-label={`Evidence record ${tx.id}`}>
        <ReconPanel title={`EVIDENCE · ${tx.id}`}>
          <div className={styles.grid}>
            <section className={styles.txBlock} aria-label="Transaction as emitted">
              <ReconRow className={styles.txRow} state="matched">
                <TraceLine />
                <dl className={styles.fields}>
                  {TX_FIELDS.map((f) => {
                    const ev = evidenceFor(f.field);
                    return (
                      <div key={f.field} className={styles.field}>
                        <dt className={styles.label}>{f.label}</dt>
                        <dd className={styles.value}>
                          {f.field === "amount" ? (
                            <SketchAnnotation kind="arrow" tone="mint" note="FOLLOW THE BOX" className={styles.arrowAt} start="top 75%" triggerSelector="figure">
                              {f.value}
                              {f.unit ? <span className={styles.unit}>{f.unit}</span> : null}
                            </SketchAnnotation>
                          ) : (
                            <>
                              {f.value}
                              {f.unit ? <span className={styles.unit}>{f.unit}</span> : null}
                            </>
                          )}
                          <span className={styles.status}>
                            {ev ? `page ${show(ev.page)} · row ${show(ev.row)}` : "no evidence entry"}
                          </span>
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </ReconRow>
              <p className={styles.meta}>
                {TRACE_SAMPLE.sampleId} · {TRACE_SAMPLE.layoutVersion} · {TRACE_SAMPLE.method}
              </p>
            </section>

            <div aria-hidden="true" className={styles.connector}>
              <Sketch kind="arrow" tone="muted" start="top 85%" triggerSelector="figure" className={styles.connectorMark} />
            </div>

            <div className={`lp-scroll lp-focusable ${styles.evBlock}`} role="region" aria-label="Evidence entries, scrollable" tabIndex={0}>
              <table className={styles.table}>
                <caption className={styles.caption}>Evidence entries for {tx.id}</caption>
                <thead>
                  <tr>
                    <th scope="col">Key</th>
                    <th scope="col">Page</th>
                    <th scope="col">Bbox</th>
                    <th scope="col">Row</th>
                    <th scope="col">Raw text</th>
                    <th scope="col">Method</th>
                    {hasConfidence ? <th scope="col">Confidence</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {TRACE_SAMPLE.evidence.map((e) => (
                    <tr key={e.key}>
                      <th scope="row" className={styles.key}>
                        {e.key}
                      </th>
                      <td>{show(e.page)}</td>
                      <td>{e.bbox ? e.bbox.join(", ") : "null"}</td>
                      <td>{show(e.row)}</td>
                      <td className={styles.raw}>{e.raw_text}</td>
                      <td>{e.method}</td>
                      {hasConfidence ? <td>{show(e.confidence)}</td> : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </ReconPanel>
      </figure>
      </WipeReveal>
      </Reveal>
    </Section>
  );
}
