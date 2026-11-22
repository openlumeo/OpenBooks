import type { RefusalCode, Stage } from "./types";

export const STAGES: { id: Stage; label: string; hint: string }[] = [
  { id: "detect", label: "Detect", hint: "Format and layout version. Unknown layouts are refused, never guessed." },
  { id: "parse", label: "Parse", hint: "Rows, pages and fields read by the layout's own parser." },
  {
    id: "normalise",
    label: "Normalise",
    hint: "Decimal money, ISO dates, currency, typed references. Parsers normalise as they read, so this completes with Parse.",
  },
  { id: "balance", label: "Balance", hint: "Opening + transactions = closing, running balance, printed totals. Decides release." },
];

export function stageForRefusal(code: RefusalCode): Stage {
  switch (code) {
    case "UNSUPPORTED_INPUT":
    case "UNKNOWN_LAYOUT":
      return "detect";
    case "PARSE_ERROR":
    case "LOW_CONFIDENCE":
      return "parse";
    case "BALANCE_MISMATCH":
    case "OUTPUT_INVALID":
      return "balance";
  }
}

export const REFUSAL_MEANING: Record<RefusalCode, string> = {
  UNKNOWN_LAYOUT: "No known layout matches this file. Open Books does not guess.",
  UNSUPPORTED_INPUT: "This file type, size or mode cannot be processed.",
  PARSE_ERROR: "A layout matched, but a field could not be read unambiguously.",
  BALANCE_MISMATCH: "The file's own numbers do not tie out, or it has no independent balance evidence.",
  LOW_CONFIDENCE: "The typed heads could not support the rule-based reading.",
  OUTPUT_INVALID: "The result failed its own schema check.",
};

export type FixField = "opening" | "currency" | "date_order";

export function fixesFor(message: string): FixField[] {
  const out: FixField[] = [];
  if (/supply --opening/.test(message)) out.push("opening");
  if (/supply --currency/.test(message)) out.push("currency");
  if (/supply --date-order/.test(message)) out.push("date_order");
  return out;
}
