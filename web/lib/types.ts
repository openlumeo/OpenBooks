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


export type Health = {
  status: "ok";
  engine_version: string;
  schema_version: string;
  ocr_available: boolean;
  ocr_issue?: string | null;
  model_weights_present: boolean;
  model_issue?: string | null;
  link_available?: boolean;
  max_bytes: number;
  allowed_extensions: string[];
};

type FormatGroup = { id: string; title: string; inputs: string[]; layouts: string[]; extensions: string[] };
export type Formats = {
  groups: FormatGroup[];
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


type RoleName = "other" | "date" | "desc" | "debit" | "credit" | "balance";

type RoleToken = {
  text: string;
  ocr_confidence?: number | null;
  ocr_text?: string;
  box: [number, number, number, number];
  role: RoleName;
  role_set: RoleName[];
  vtype: "text" | "date" | "money" | "code";
  type_set: string[];
  abstained: boolean;
};

export type RolesDoc = {
  schema_version: "openbooks.roles.v1";
  method: "pdf_text" | "ocr";
  pages: { page: number; width: number; height: number; tokens: RoleToken[] }[];
  summary: { tokens: number; abstained: number; abstain_rate: number; by_role: Record<string, number>; inference_ms: number; device: string };
  model: { weights_sha256: string; calibration_sha256: string };
};


export type RunParams = {
  currency?: string;
  opening?: string;
  account?: string;
  allow_derived_opening?: boolean;
  ocr?: boolean;
  model?: boolean;
  date_order?: "dmy" | "mdy";
};


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
  sourceTurnId: string;
  files: FileRun[];
  state: "running" | "done" | "error";
  error?: string;
  linkError?: string;
};

export type UserAskTurn = { id: string; kind: "user-ask"; at: number; text: string };

type ToolTrace = { name: string; summary: string };

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
