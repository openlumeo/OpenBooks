import { z } from "zod";
import type { EngineDoc } from "../types";

export const Amount = z.string().regex(/^-?\d+(\.\d+)?$/, "plain decimal like 1000.00");
export const IsoDate = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "YYYY-MM-DD");

const Text = z.string();
const Sha = Text.regex(/^[0-9a-f]{64}$/);
const Currency = Text.regex(/^[A-Z]{3}$/);
const Money = z.looseObject({ amount: Amount, currency: Currency });
const OptionalMoney = Money.optional();
const Transaction = z.looseObject({
  id: Text,
  batch_id: Text,
  account_id: Text.optional(),
  date: IsoDate.optional(),
  direction: z.enum(["credit", "debit"]).optional(),
  kind: Text.optional(),
  description: Text.nullable().optional(),
  reference: Text.nullable().optional(),
  deductor: Text.nullable().optional(),
  remitter: Text.nullable().optional(),
  account: Text.nullable().optional(),
  category: Text.nullable().optional(),
  amount: OptionalMoney,
  balance_after: OptionalMoney,
  gross: OptionalMoney,
  fee: OptionalMoney,
  tax: OptionalMoney,
  net: OptionalMoney,
  inr_amount: OptionalMoney,
  reported_value: OptionalMoney,
  gain_loss: OptionalMoney,
  proceeds: OptionalMoney,
  cost_basis: OptionalMoney,
  tax_deducted: OptionalMoney,
  debit: OptionalMoney,
  credit: OptionalMoney,
});
const Evidence = z.looseObject({
  page: z.number().int().nullable(),
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullable(),
  row: z.number().int().nullable(),
  raw_text: Text,
  method: Text,
  confidence: z.number().optional(),
});
const Assertion = z.looseObject({
  id: Text, rule: Text, expected: Text, computed: Text, passed: z.literal(true), independent: z.boolean(),
});
const Released = z.object({
  schema_version: z.literal("openbooks.v1"),
  status: z.literal("ok"),
  file: z.object({
    sha256: Sha, name: Text, detected_format: Text, layout_version: Text, method: Text,
    model: z.object({ weights_sha256: Sha, calibration_sha256: Sha }).optional(),
  }),
  data: z.object({
    accounts: z.array(z.looseObject({ id: Text, number: Text.nullable().default(null), currency: Currency })),
    parties: z.array(z.unknown()),
    batches: z.array(z.looseObject({
      id: Text,
      kind: z.enum(["statement", "settlement", "tax_statement", "ais", "fira", "trial_balance", "form_1099b"]),
      currency: Currency,
      account_id: Text.optional(),
      period_start: IsoDate.optional(),
      period_end: IsoDate.optional(),
      opening: OptionalMoney,
      closing: OptionalMoney,
      stated_closing: OptionalMoney,
      payout: Money.nullable().optional(),
      opening_derived: z.boolean().optional(),
      source_method: Text.optional(),
      totals_are_formulas: z.boolean().optional(),
      no_movement: z.array(z.object({ after: Text, balance: Money })).optional(),
    })),
    transactions: z.array(Transaction).min(1),
    claims: z.array(z.unknown()),
  }),
  evidence: z.record(Text, Evidence),
  assertions: z.array(Assertion).refine((items) => items.some((item) => item.independent), "an independent assertion is required"),
});
const Refused = z.object({
  schema_version: z.literal("openbooks.v1"),
  status: z.literal("refused"),
  data: z.null(),
  error: z.looseObject({
    code: z.enum(["UNKNOWN_LAYOUT", "UNSUPPORTED_INPUT", "PARSE_ERROR", "BALANCE_MISMATCH", "LOW_CONFIDENCE", "OUTPUT_INVALID"]),
    message: Text,
    file_sha256: Sha,
  }),
});

// Browser-supplied documents need the shape consumed by the digest and tools. Source verification belongs to the engine.
const Document: z.ZodType<EngineDoc> = z.discriminatedUnion("status", [Released, Refused]);
export const AskBody = z.object({
  question: Text.trim().min(1).max(4000),
  history: z.array(z.object({ role: z.enum(["user", "assistant"]), content: Text.max(20000) })).max(40),
  docs: z.array(z.object({ file: Text.min(1).max(300), doc: Document })).max(200)
    .refine((docs) => new Set(docs.map(({ file }) => file)).size === docs.length, "file keys must be unique"),
});
