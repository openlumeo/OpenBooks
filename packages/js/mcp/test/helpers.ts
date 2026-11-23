import type { Engine, RunResult } from "@lumeo_hq/openbooks-core";
import type { Doc, ExecuteResult } from "../src/operations.js";
import type { Operations } from "../src/operations.js";

export const ENGINE: Engine = {
  python: ["python"],
  info: {
    name: "openbooks",
    version: "9.9.9",
    schema_version: "openbooks.v1",
    layout_api: 1,
    python: "3.12.0",
    layouts: ["bank_csv", "bank_pdf", "stripe"],
    known_layouts: [
      { id: "bank_csv", distribution: "openbooks" },
      { id: "stripe", distribution: "openbooks-gateways" },
    ],
    frontends: ["document", "csv"],
    linker: true,
  },
};

export function released(file: string, extra: Doc = {}): RunResult {
  const document = {
    schema_version: "openbooks.v1",
    status: "ok",
    file,
    data: {
      opening: "1000.00",
      accounts: [{ id: "acc1" }],
      transactions: [{ id: "t1" }, { id: "t2" }, { id: "t3" }],
      batches: [],
    },
    evidence: { "t1.amount": { page: 1 }, "t2.amount": { page: 2 } },
    assertions: [{ id: "as1" }, { id: "as2" }],
    ...extra,
  };
  return { kind: "released", file, document } as unknown as RunResult;
}

export function refused(file: string, code = "BALANCE_MISMATCH", message = "totals differ"): RunResult {
  const document = { schema_version: "openbooks.v1", status: "refused", file, data: null, error: { code, message } };
  return { kind: "refused", file, code, message, document, internal: false, restricted: false } as unknown as RunResult;
}

export const encode = (value: string | Buffer): string => Buffer.from(value).toString("base64");

export async function call(operations: Operations, operation: string, args: Doc = {}, id = "s1"): Promise<Doc> {
  const outcome: ExecuteResult = await operations.execute([{ id, operation, arguments: args }]);
  const item = outcome.steps?.[0];
  if (item === undefined) throw new Error("execute returned no step");
  return item;
}

export const errorCode = (item: Doc): string | undefined => (item.error as { code?: string } | undefined)?.code;
export const resultOf = (item: Doc): Doc => (item.result ?? {}) as Doc;
export const sleep = (ms: number): Promise<void> => new Promise((resolve) => setTimeout(resolve, ms));
