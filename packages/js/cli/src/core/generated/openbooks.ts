// GENERATED from schema/*.json by scripts/generate-types.mjs. Do not edit; run `pnpm generate`.

export interface OpenBooksDocument {
  schema_version: "openbooks.v1";
  status: "ok";
  file: {
    sha256: string;
    model?: {
      weights_sha256: string;
      calibration_sha256: string;
    };
    name: string;
    detected_format: string;
    layout_version: string;
    method: string;
    [k: string]: unknown;
  };
  data: {
    accounts: Account[];
    parties: {
      [k: string]: unknown;
    }[];
    batches: Batch[];
    /**
     * @minItems 1
     */
    transactions: [Transaction, ...Transaction[]];
    claims: {
      [k: string]: unknown;
    }[];
    [k: string]: unknown;
  };
  evidence: {
    [k: string]: Evidence;
  };
  /**
   * @minItems 1
   */
  assertions: [Assertion, ...Assertion[]];
  [k: string]: unknown;
}
export interface Account {
  id: string;
  number?: string | null;
  currency: string;
  [k: string]: unknown;
}
export interface Batch {
  id: string;
  kind: string;
  currency: string;
  account_id?: string;
  period_start?: string;
  period_end?: string;
  opening?: Money;
  closing?: Money;
  stated_closing?: Money;
  payout?: Money | null;
  opening_derived?: boolean;
  source_method?: string;
  totals_are_formulas?: boolean;
  no_movement?: {
    after: string;
    balance: Money;
    [k: string]: unknown;
  }[];
  [k: string]: unknown;
}
export interface Money {
  amount: string;
  currency: string;
}
export interface Transaction {
  id: string;
  batch_id: string;
  account_id?: string;
  date?: string;
  direction?: "credit" | "debit";
  amount?: Money;
  balance_after?: Money;
  gross?: Money;
  fee?: Money;
  tax?: Money;
  net?: Money;
  kind?: string;
  description?: string;
  reference?: string | null;
  [k: string]: unknown;
}
export interface Evidence {
  page: number | null;
  /**
   * @minItems 4
   * @maxItems 4
   */
  bbox: [number, number, number, number] | null;
  row: number | null;
  raw_text: string;
  method: string;
  confidence?: number;
  [k: string]: unknown;
}
export interface Assertion {
  id: string;
  rule: string;
  expected: string;
  computed: string;
  passed: boolean;
  independent: boolean;
  [k: string]: unknown;
}

export interface OpenBooksRefusal {
  schema_version: "openbooks.v1";
  status: "refused";
  data: null;
  error: {
    code: string;
    message: string;
    internal?: boolean;
    file_sha256: string;
  };
}
