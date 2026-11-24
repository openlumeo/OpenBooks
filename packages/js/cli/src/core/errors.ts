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
  readonly hint?: string;
  constructor(kind: EngineErrorKind, message: string, hint?: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "EngineError";
    this.kind = kind;
    this.hint = hint;
  }
}

export const INSTALL_HINT = "pip install openbooks, then run: openbooks doctor";
