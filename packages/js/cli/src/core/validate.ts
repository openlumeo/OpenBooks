import { readFileSync } from "node:fs";
import { Ajv2020 } from "ajv/dist/2020.js";
import type { ValidateFunction } from "ajv/dist/2020.js";
import type { OpenBooksDocument, OpenBooksRefusal } from "./generated/openbooks.js";

const load = (name: string): object => JSON.parse(readFileSync(new URL(`../../schema/${name}`, import.meta.url), "utf8")) as object;

let compiled: { document: ValidateFunction; refusal: ValidateFunction } | undefined;

function validators() {
  if (!compiled) {
    const ajv = new Ajv2020({ strict: true, allowUnionTypes: true, allErrors: false });
    compiled = { document: ajv.compile(load("openbooks.v1.schema.json")), refusal: ajv.compile(load("openbooks.v1.refusal.schema.json")) };
  }
  return compiled;
}

function describe(v: ValidateFunction): string {
  const e = v.errors?.[0];
  return e ? `${e.instancePath || "/"} ${e.message ?? "is invalid"}` : "is invalid";
}

export function validateDocument(x: unknown): asserts x is OpenBooksDocument {
  const v = validators().document;
  if (!v(x)) throw new Error(`not a valid openbooks.v1 document: ${describe(v)}`);
}

export function validateRefusal(x: unknown): asserts x is OpenBooksRefusal {
  const v = validators().refusal;
  if (!v(x)) throw new Error(`not a valid openbooks.v1 refusal: ${describe(v)}`);
}
