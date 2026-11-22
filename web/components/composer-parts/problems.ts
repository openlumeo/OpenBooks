import { fmtBytes } from "../../lib/format";
import type { RunParams } from "../../lib/types";
import type { Workspace } from "../../lib/use-workspace";

export const MAX_FILES = 20;
const IMAGE_NAME = /\.(png|jpe?g)$/i;

export type Pending = { id: string; file: File; params?: RunParams; sample?: string };

export function fileExtension(name: string): string {
  return name.includes(".") ? name.slice(name.lastIndexOf(".")).toLowerCase() : "";
}

export function isImageName(name: string): boolean {
  return IMAGE_NAME.test(name);
}

export function isOverLimit(pending: Pending, allowed: string[], maxBytes: number): boolean {
  const unsupported = allowed.length > 0 && !allowed.includes(fileExtension(pending.file.name));
  return pending.file.size > maxBytes || unsupported;
}

export function problemsFor(pending: Pending[], allowed: string[], maxBytes: number): string | null {
  if (pending.length > MAX_FILES) return `At most ${MAX_FILES} files per run. Remove ${pending.length - MAX_FILES}.`;
  const unsupported = pending.find((p) => allowed.length > 0 && !allowed.includes(fileExtension(p.file.name)));
  if (unsupported) return `${unsupported.file.name} is not a supported type. Accepted: ${allowed.join(" ")}.`;
  const oversized = pending.find((p) => p.file.size > maxBytes);
  if (oversized) return `${oversized.file.name} is over the ${fmtBytes(maxBytes)} limit.`;
  return null;
}

export type HintInput = {
  operation: Workspace["operation"];
  engineUp: boolean;
  problem: string | null;
  hasFiles: boolean;
  hasImage: boolean;
  hasText: boolean;
  hasDocs: boolean;
  askEnabled: boolean | null;
  ocrIssue?: string | null;
};

export function composerHint(input: HintInput): string {
  if (input.operation === "link") return "Checking links across released files.";
  if (input.operation === "history") return "Updating browser history.";
  if (!input.engineUp) return "The engine is not reachable, so files cannot be checked right now.";
  if (input.problem) return input.problem;
  if (input.hasFiles && input.ocrIssue && input.hasImage) return input.ocrIssue;
  if (input.hasFiles) return "Each file is checked on its own. Nothing is released unless its numbers tie out.";
  if (input.askEnabled === false && (input.hasText || input.hasDocs)) {
    return "Questions need OPENBOOKS_LLM_API_KEY and OPENBOOKS_LLM_MODEL on the web server. File checks still work.";
  }
  return input.askEnabled ? "Enter to send · Shift+Enter for a new line" : "Attach files to begin";
}
