"use client";

import { FlaskConical, Plus } from "lucide-react";
import { AgentQuickStart } from "@/components/onboard/agent-onboarding";
import { STAGES } from "@/lib/stages";
import type { Formats, Sample } from "@/lib/types";

export function EmptyState({
  formats,
  samples,
  onSample,
  engineUp,
}: {
  formats: Formats | null;
  samples: Sample[];
  onSample: (s: Sample) => void;
  engineUp: boolean;
}) {
  const featured = samples.filter((s) => s.featured);
  return (
    <div className="ob-empty">
      <div className="ob-empty-head">
        <h1 className="t-display t-h2">Proven JSON, or a typed refusal.</h1>
        <p className="t-lede">
          Drop in bank statements, gateway settlements, tax documents or workpapers. Each file comes back as one
          openbooks.v1 document whose own numbers tie out, or a refusal that says exactly why. Then ask about what was
          released.
        </p>
        <span className="ob-empty-maturity mono-label">
          <FlaskConical size={13} aria-hidden="true" /> Early release · tested on synthetic data only
        </span>
      </div>

      <section className="ob-section" aria-labelledby="agent-title">
        <h2 id="agent-title" className="ob-section-title">
          Connect your AI agent
        </h2>
        <AgentQuickStart workspaceHref="/get-started" />
      </section>

      <ol className="ob-pipeline" aria-label="What happens to each file">
        {STAGES.map((s, i) => (
          <li key={s.id} className="ob-pipeline-step">
            <span className="mono-label">
              {i + 1} · {s.label}
            </span>
            <p>{s.hint.split(". ")[0]!.replace(/\.$/, "")}.</p>
          </li>
        ))}
      </ol>

      {featured.length > 0 && (
        <section className="ob-section" aria-labelledby="samples-title">
          <h2 id="samples-title" className="ob-section-title">
            Try it on a sample
          </h2>
          <p className="t-body-sm">
            Synthetic files from the engine&apos;s golden set. Some tie out; some were tampered with on purpose and must
            be refused.
          </p>
          <div className="ob-samples">
            {featured.map((s) => (
              <button key={s.id} type="button" className="ob-sample" onClick={() => onSample(s)} disabled={!engineUp}>
                <span>
                  <span className="ob-sample-name">{s.label}</span>
                  <span className="ob-sample-file">{s.filename}</span>
                </span>
                {s.expect_status === "ok" ? (
                  <span className="tag tag--ok">Releases</span>
                ) : (
                  <span className="tag tag--bad">
                    <span className="dot" />
                    Refuses · {s.expect_code}
                  </span>
                )}
                <Plus size={16} className="ob-sample-add" aria-hidden="true" />
              </button>
            ))}
          </div>
        </section>
      )}

      {formats && (
        <section className="ob-section" aria-labelledby="reads-title">
          <h2 id="reads-title" className="ob-section-title">
            What it reads
          </h2>
          <table className="ob-spec">
            <tbody>
              {formats.groups.map((g) => (
                <tr key={g.id}>
                  <th scope="row">{g.title}</th>
                  <td>{g.inputs.join(" · ")}</td>
                  <td className="ob-spec-layouts">{g.layouts.join("  ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="t-body-sm">
            Up to 20 files per run, {Math.round(formats.max_bytes / (1024 * 1024))} MB each.
            {formats.unverified && formats.unverified.length > 0 && (
              <>
                {" "}
                The {formats.unverified.map((u) => u.name).join(", ")} layouts follow public descriptions of those
                exports and have been tested on synthetic files only.
              </>
            )}
          </p>
        </section>
      )}
    </div>
  );
}
