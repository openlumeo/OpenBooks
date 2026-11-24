import { Section } from "./section";
import { INPUT_GROUPS, UNVERIFIED, UNVERIFIED_NOTE } from "./inputs-data";
import { InputsTrack } from "./inputs-track";
import styles from "./inputs.module.css";

function FileGlyph() {
  return (
    <svg aria-hidden="true" focusable="false" className={styles.glyph} viewBox="0 0 20 24" width="16" height="20">
      <path
        d="M2.5 1.5h10.2l4.8 4.9v16.1H2.5Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.25"
        strokeLinejoin="round"
      />
      <path d="M12.6 1.8v4.6h4.6" fill="none" stroke="currentColor" strokeWidth="1.25" strokeLinejoin="round" />
      <path
        d="M5 11.5h8M5 14.5h7M5 17.5h5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        strokeLinecap="round"
      />
    </svg>
  );
}

function isUnverified(name: string): boolean {
  return UNVERIFIED.some((u) => u.name === name);
}

export function Inputs() {
  return (
    <Section id="inputs" heading="The files your clients actually send.">
      <p className="t-lede">
        Bank statements, gateway settlements, tax records and workpapers, in the formats they arrive in. Up to 20 MB per
        file.
      </p>
      <InputsTrack>
        <ul className={styles.list}>
          {INPUT_GROUPS.map((group, index) => (
            <li key={group.id} className={styles.group}>
              <header className={styles.head}>
                <h3 className={`t-card-title ${styles.term}`}>{group.title}</h3>
                <span aria-hidden="true" className={styles.count}>
                  {String(index + 1).padStart(2, "0")}
                </span>
              </header>

              <p className={styles.label}>Inputs</p>
              <ul className={styles.files}>
                {group.inputs.map((name) => (
                  <li key={name} className={styles.file}>
                    <FileGlyph />
                    <span>{name}</span>
                    {isUnverified(name) ? <span className={styles.tag}>PREVIEW</span> : null}
                  </li>
                ))}
              </ul>

              <p className={styles.label}>Layouts</p>
              <ul className={styles.ids}>
                {group.layouts.map((layout) => (
                  <li key={layout}>{layout}</li>
                ))}
              </ul>

              <p className={styles.label}>Extensions</p>
              <ul className={styles.exts}>
                {group.extensions.map((ext) => (
                  <li key={ext}>{ext}</li>
                ))}
              </ul>

              {group.note ? <p className={styles.note}>{group.note}</p> : null}
            </li>
          ))}
        </ul>
      </InputsTrack>
      <div className={styles.footnotes}>
        <p className={styles.note}>
          <span className={styles.tag}>PREVIEW</span> {UNVERIFIED_NOTE}
        </p>
      </div>
    </Section>
  );
}
