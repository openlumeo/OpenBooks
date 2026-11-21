import type { RunResult } from "@lumeo_hq/openbooks-core";
import type { DoctorReport } from "@lumeo_hq/openbooks-doctor";

/** One line per file: "<file>: released <layout>" or "<file>: refused <CODE>: <message>". */
export function formatRunText(results: readonly RunResult[]): string {
  return results
    .map((r) => (r.kind === "released"
      ? `${r.file}: released ${r.document.file.layout_version}\n`
      : `${r.file}: refused ${r.code}: ${r.message}\n`))
    .join("");
}

/** The JSON array printed by --json. Refusals carry their code and message next to the document. */
export function formatRunJson(results: readonly RunResult[]): string {
  const items = results.map((r) => ({
    file: r.file,
    status: r.kind,
    ...(r.kind === "refused" ? { code: r.code, message: r.message } : {}),
    document: r.document,
  }));
  return JSON.stringify(items, null, 2) + "\n";
}

const FIX_STATUSES = new Set(["fail", "warn"]);

/** The human-readable doctor report: one line per check, a fix line under failures and warnings, then a summary. */
export function formatDoctorText(report: DoctorReport): string {
  const checks = report.checks.map((c) => {
    const fix = c.fix && FIX_STATUSES.has(c.status) ? `       fix: ${c.fix}\n` : "";
    return `[${c.status.padEnd(4)}] ${c.id}: ${c.detail}\n${fix}`;
  });
  const { pass, warn, fail, skip } = report.summary;
  const verdict = report.ok ? "OK" : "NOT OK";
  return `${checks.join("")}${pass} passed, ${warn} warnings, ${fail} failed, ${skip} skipped -> ${verdict}\n`;
}
