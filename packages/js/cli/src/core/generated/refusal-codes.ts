// GENERATED from packages/py/openbooks/src/openbooks/core/refusal_codes.py by scripts/sync_schemas.py. Do not edit.
export const REFUSAL_CODES: Readonly<Record<string, string>> = {
  "UNKNOWN_LAYOUT": "No known layout matched, or a required provider is missing. Check the source export and installed providers.",
  "UNSUPPORTED_INPUT": "Type, size, encoding or structure is outside supported inputs. Check the extension, size, locked PDFs and OCR availability.",
  "AMBIGUOUS_DATE": "A day/month order could not be proven from the file. Declare the date order (dmy or mdy) explicitly and rerun.",
  "PARSE_ERROR": "A required field could not be read. Check the opening balance, date order, currency and the field named in the message.",
  "BALANCE_MISMATCH": "A reconciliation assertion failed or evidence was insufficient. Compare printed running balances and totals against the original and look for missing rows.",
  "LOW_CONFIDENCE": "OCR or model-assisted reading could not be supported with enough confidence. Review scan quality, orientation and column labels.",
  "OUTPUT_INVALID": "The result failed contract validation. Record the engine version and report a minimal synthetic reproduction."
};
