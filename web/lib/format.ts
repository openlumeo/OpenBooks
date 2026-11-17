export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10 * 1024 ? 1 : 0)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

const rtf = typeof Intl !== "undefined" ? new Intl.RelativeTimeFormat("en-IN", { numeric: "auto" }) : null;

export function fmtAgo(ts: number, now = Date.now()): string {
  const s = Math.round((ts - now) / 1000);
  const abs = Math.abs(s);
  if (!rtf) return new Date(ts).toLocaleString();
  if (abs < 45) return "just now";
  if (abs < 3600) return rtf.format(Math.round(s / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(s / 3600), "hour");
  if (abs < 86400 * 7) return rtf.format(Math.round(s / 86400), "day");
  return new Date(ts).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

export function uid(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
}

/** Trigger a download of text as a file. */
export function downloadText(filename: string, text: string, type = "application/json") {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function jsonFileName(name: string): string {
  return `${name.replace(/\.[^.]+$/, "") || "file"}.openbooks.json`;
}

export function paramSummary(p: {
  currency?: string;
  opening?: string;
  account?: string;
  allow_derived_opening?: boolean;
  ocr?: boolean;
  model?: boolean;
  date_order?: "dmy" | "mdy";
}): string {
  const parts: string[] = [];
  if (p.currency) parts.push(p.currency);
  if (p.opening) parts.push(`opening ${p.opening}`);
  if (p.account) parts.push(`acct ${p.account}`);
  if (p.allow_derived_opening) parts.push("derived opening allowed");
  if (p.date_order) parts.push(p.date_order === "dmy" ? "day-first dates" : "month-first dates");
  if (p.ocr === false) parts.push("no OCR");
  if (p.model) parts.push("model cross-check");
  return parts.join(" · ");
}
