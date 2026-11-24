import type { Assertion } from "@/lib/types";

export function AssertionsTab({ assertions }: { assertions: Assertion[] }) {
  return (
    <div className="panel">
      <p className="t-body-sm">
        Each check compares what the file states with what its own rows compute. A file is released only when every
        check ties and at least one is independent: it uses a figure printed in the document, not the parser&apos;s own
        arithmetic.
      </p>
      <ul className="recon-list">
        {assertions.map((a) => (
          <li key={a.id} className={`assert-row${a.passed ? "" : " assert-row--bad"}`}>
            <span className="assert-rule">{a.rule}</span>
            <span className="assert-flags">
              {a.independent && <span className="tag">Independent</span>}
              <span className={`tag ${a.passed ? "tag--ok" : "tag--bad"}`}>{a.passed ? "Ties" : "Fails"}</span>
            </span>
            <span className="assert-vals">
              <span>
                <b>Expected</b>
                {a.expected}
              </span>
              <span>
                <b>Computed</b>
                {a.computed}
              </span>
              <span>
                <b>Id</b>
                {a.id}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
