/**
 * A refusal is a valid financial outcome and is returned as a value. Everything here is the other kind of failure: the
 * engine could not do its job, so nothing can be said about the document.
 */
export type EngineErrorKind =
  | "python_not_found"
  | "engine_not_installed"
  | "engine_version"
  | "engine_fault"
  | "timeout"
  | "aborted"
  | "bad_output"
  | "input";

export class EngineError extends Error {
  readonly kind: EngineErrorKind;
  /** What to run to fix it, when there is an obvious answer. */
  readonly hint?: string;
  constructor(kind: EngineErrorKind, message: string, hint?: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "EngineError";
    this.kind = kind;
    this.hint = hint;
  }
}

export const INSTALL_HINT = "pip install openbooks   (or: pip install openbooks-core plus the provider packages you need), then run: openbooks doctor";
