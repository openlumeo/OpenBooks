import { Check, X } from "lucide-react";
import { STAGES, stageForRefusal } from "@/lib/stages";
import type { FileRun } from "@/lib/types";

type State = "done" | "active" | "stopped" | "pending";

function stageStates(f: FileRun): State[] {
  const doc = f.doc;
  if (doc?.status === "ok") return STAGES.map(() => "done");
  if (doc?.status === "refused") {
    const stopAt = stageForRefusal(doc.error.code);
    const stop = STAGES.findIndex((s) => s.id === stopAt);
    return STAGES.map((_, i) => (i < stop ? "done" : i === stop ? "stopped" : "pending"));
  }
  if (f.state === "running") {
    const firstOpen = STAGES.findIndex((s) => !f.stages.includes(s.id));
    return STAGES.map((s, i) => (f.stages.includes(s.id) ? "done" : i === firstOpen ? "active" : "pending"));
  }
  return STAGES.map(() => "pending");
}

export function StageTrail({ file }: { file: FileRun }) {
  const states = stageStates(file);
  return (
    <ol className="stages" aria-label="Pipeline stages">
      {STAGES.map((s, i) => {
        const st = states[i]!;
        const word =
          st === "done"
            ? "passed"
            : st === "stopped"
              ? "stopped here"
              : st === "active"
                ? "in progress"
                : "not reached";
        return (
          <li key={s.id} className={`stage stage--${st}`} title={s.hint}>
            <span className="stage-mark" aria-hidden="true">
              {st === "done" ? (
                <Check size={13} strokeWidth={2} />
              ) : st === "stopped" ? (
                <X size={13} strokeWidth={2} />
              ) : st === "active" ? (
                <span className="dot dot--live" />
              ) : (
                <span className="dot" />
              )}
            </span>
            <span className="stage-label">{s.label}</span>
            <span className="sr-only">: {word}</span>
          </li>
        );
      })}
    </ol>
  );
}
