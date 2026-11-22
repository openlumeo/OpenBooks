// Section 5: what the engine reads. Server component. Data from inputs-data.ts (catalog.py).
import { Section } from "./section";
import { INPUT_GROUPS, UNVERIFIED, UNVERIFIED_NOTE } from "./inputs-data";
import styles from "./inputs.module.css";

export function Inputs() {
  return (
    <Section id="inputs" heading="The files your clients actually send.">
      <p className="t-lede">
        Bank statements, gateway settlements, tax records and workpapers, in the formats they arrive in. Up to 20 MB per
        file.
      </p>
      <dl className={styles.list}>
        {INPUT_GROUPS.map((group) => (
          <div key={group.id} className={styles.group}>
            <dt className={`t-card-title ${styles.term}`}>{group.title}</dt>
            <dd className={styles.def}>
              <dl className={styles.facts}>
                <dt className={styles.label}>Inputs</dt>
                <dd className={styles.inputs}>
                  {group.inputs.map((name, i) => {
                    const unverified = UNVERIFIED.some((u) => u.name === name);
                    return (
                      <span key={name} className={styles.input}>
                        {name}
                        {unverified ? <span className={styles.tag}>PREVIEW</span> : null}
                        {i < group.inputs.length - 1 ? <span aria-hidden="true" className={styles.sep}>,</span> : null}
                      </span>
                    );
                  })}
                </dd>
                <dt className={styles.label}>Layouts</dt>
                <dd>
                  <ul className={styles.ids}>
                    {group.layouts.map((layout) => (
                      <li key={layout}>{layout}</li>
                    ))}
                  </ul>
                </dd>
                <dt className={styles.label}>Extensions</dt>
                <dd>
                  <ul className={styles.ids}>
                    {group.extensions.map((ext) => (
                      <li key={ext}>{ext}</li>
                    ))}
                  </ul>
                </dd>
              </dl>
              {group.note ? <p className={styles.note}>{group.note}</p> : null}
            </dd>
          </div>
        ))}
      </dl>
      <div className={styles.footnotes}>
        <p className={styles.note}>
          <span className={styles.tag}>PREVIEW</span> {UNVERIFIED_NOTE}
        </p>
      </div>
    </Section>
  );
}
