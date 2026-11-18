// openbooks.v1 as the engine emits it (src/openbooks/pipeline.py SCHEMA, parsers_extra.py).
// Amounts are decimal STRINGS. Never convert them with Number(): see lib/query.ts.

export type Money = { amount: string; currency: string };

export type RefusalCode =
  | "UNKNOWN_LAYOUT"
  | "UNSUPPORTED_INPUT"
  | "PARSE_ERROR"
  | "BALANCE_MISMATCH"
  | "LOW_CONFIDENCE"
  | "OUTPUT_INVALID";

export type BatchKind = "statement" | "settlement" | "tax_statement" | "ais" | "fira" | "trial_balance" | "form_1099b";

export type Account = { id: string; number: string | null; currency: string };

export type Batch = {
  id: string;
  kind: BatchKind;
  currency: string;
  account_id?: string;
  period_start?: string;
  period_end?: string;
  opening?: Money;
  closing?: Money;
  opening_derived?: boolean;
  stated_closing?: Money;
  payout?: Money | null;
  source_method?: string;
  totals_are_formulas?: boolean;
  no_movement?: { after: string; balance: Money }[];
  [extra: string]: unknown;
};

export type Transaction = {
  id: string;
  batch_id: string;
  account_id?: string;
  date?: string;
  direction?: "credit" | "debit";
  amount?: Money;
  balance_after?: Money;
  description?: string | null;
  reference?: string | null;
  kind?: string;
  [extra: string]: unknown;
};

export type Evidence = {
  page: number | null;
  bbox: [number, number, number, number] | null;
  row: number | null;
  raw_text: string;
  method: string;
  confidence?: number;
};

export type Assertion = {
  id: string;
  rule: string;
  expected: string;
  computed: string;
  passed: boolean;
  independent: boolean;
};

export type ReleasedDoc = {
  schema_version: "openbooks.v1";
  status: "ok";
  file: {
    sha256: string;
    name: string;
    detected_format: string;
    layout_version: string;
    method: string;
    /** present on a --model release: the exact weights and calibration that cross-checked it */
    model?: { weights_sha256: string; calibration_sha256: string };
  };
  data: {
    accounts: Account[];
    parties: unknown[];
    batches: Batch[];
    transactions: Transaction[];
    claims: unknown[];
  };
  evidence: Record<string, Evidence>;
  assertions: Assertion[];
};

export type RefusedDoc = {
  schema_version: "openbooks.v1";
  status: "refused";
  data: null;
  error: { code: RefusalCode; message: string; file_sha256: string };
};

export type EngineDoc = ReleasedDoc | RefusedDoc;

export type Link = {
  id: string;
  kind: "one_to_one" | "many_to_one";
  credit: string;
  sources: string[];
  amount: Money;
  evidence: string[];
  assertion: { rule: string; expected: string; computed: string; passed: boolean };
};

export type LinkReport = {
  schema_version: "openbooks.links.v1";
  links: Link[];
  ambiguous: { source?: string; credit: string; sources?: string[][]; reason: string }[];
  unlinked_sources: string[];
  unlinked_credits: string[];
  inputs: string[];
};

// ---- engine service metadata -------------------------------------------------

export type Health = {
  status: "ok";
  engine_version: string;
  schema_version: string;
  ocr_available: boolean;
  /** true only when a --model run would load (weights, matching calibration, PyTorch) */
  model_weights_present: boolean;
  model_issue?: string | null;
  max_bytes: number;
  allowed_extensions: string[];
};

export type FormatGroup = { id: string; title: string; inputs: string[]; layouts: string[]; extensions: string[] };
export type Formats = {
  groups: FormatGroup[];
  /** layouts built from public descriptions, tested on synthetic files only */
  unverified?: { layout: string; name: string }[];
  allowed_extensions: string[];
  max_bytes: number;
};

export type Sample = {
  id: string;
  filename: string;
  label: string;
  featured: boolean;
  expect_status: "ok" | "refused";
  expect_code: RefusalCode | null;
  params: RunParams;
};

// ---- typed heads' own reading (mirrors server/openbooks_server/inference.py infer_file) ------

export type RoleName = "other" | "date" | "desc" | "debit" | "credit" | "balance";

export type RoleToken = {
  text: string;
  /** [x0, y0, x1, y1] as fractions of the page, origin top-left */
  box: [number, number, number, number];
  role: RoleName;
  /** conformal set: every role the model cannot rule out */
  role_set: RoleName[];
  vtype: "text" | "date" | "money" | "code";
  type_set: string[];
  /** the role set is not exactly one role: the model declines to commit */
  abstained: boolean;
};

export type RolesDoc = {
  schema_version: "openbooks.roles.v1";
  method: "pdf_text" | "ocr";
  pages: { page: number; width: number; height: number; tokens: RoleToken[] }[];
  summary: { tokens: number; abstained: number; abstain_rate: number; by_role: Record<string, number>; inference_ms: number; device: string };
  /** the exact weights and calibration that produced this reading */
  model: { weights_sha256: string; calibration_sha256: string };
};

// ---- run params (mirrors server/openbooks_server/runs.py parse_params) ---------

export type RunParams = {
  currency?: string;
  opening?: string;
  account?: string;
  allow_derived_opening?: boolean;
  ocr?: boolean;
  model?: boolean;
  /** numeric dates: day-first or month-first; unset lets the engine prove it from the file */
  date_order?: "dmy" | "mdy";
};

// ---- conversation --------------------------------------------------------------

export type Stage = "detect" | "parse" | "normalise" | "balance" | "validate";

export type FileRun = {
  index: number;
  name: string;
  size: number;
  stages: Stage[];
  state: "queued" | "running" | "done" | "interrupted";
  doc?: EngineDoc;
  params: RunParams;
};

export type UserRunTurn = {
  id: string;
  kind: "user-run";
  at: number;
  files: { name: string; size: number }[];
  params: RunParams;
  note?: string;
};

export type RunTurn = {
  id: string;
  kind: "run";
  at: number;
  /** id of the user turn whose files these are; the File objects live in lib/session-files.ts */
  sourceTurnId: string;
  files: FileRun[];
  state: "running" | "done" | "error";
  error?: string;
};

export type UserAskTurn = { id: string; kind: "user-ask"; at: number; text: string };

export type ToolTrace = { name: string; summary: string };

export type AnswerTurn = {
  id: string;
  kind: "answer";
  at: number;
  text: string;
  tools: ToolTrace[];
  state: "streaming" | "done" | "error";
  error?: string;
};

export type LinksTurn = { id: string; kind: "links"; at: number; report: LinkReport; names: Record<string, string> };

export type Turn = UserRunTurn | RunTurn | UserAskTurn | AnswerTurn | LinksTurn;

export type Thread = { id: string; title: string; createdAt: number; updatedAt: number; turns: Turn[] };

export function isReleased(doc: EngineDoc | undefined): doc is ReleasedDoc {
  return !!doc && doc.status === "ok";
}
