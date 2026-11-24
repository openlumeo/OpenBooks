import type { RunParams } from "@/lib/types";

export type ParamsDraft = { currency: string; opening: string; account: string };

const CURRENCY_PATTERN = /^[A-Za-z]{3}$/;
const AMOUNT_PATTERN = /^-?\d+(\.\d+)?$/;

export const isCurrencyInvalid = (currency: string): boolean =>
  currency !== "" && !CURRENCY_PATTERN.test(currency.trim());

export const isOpeningInvalid = (opening: string): boolean =>
  opening !== "" && !AMOUNT_PATTERN.test(opening.replace(/,/g, "").trim());

export function draftError(draft: ParamsDraft): string | null {
  if (isCurrencyInvalid(draft.currency)) return "Currency must be three letters, like INR.";
  if (isOpeningInvalid(draft.opening)) return "Opening balance must be a plain number, like 1000.00.";
  return null;
}

export function draftToParams(params: RunParams, draft: ParamsDraft): RunParams {
  const next: RunParams = { ...params };
  if (draft.currency.trim()) next.currency = draft.currency.trim().toUpperCase();
  else delete next.currency;
  if (draft.opening.trim()) next.opening = draft.opening.replace(/,/g, "").trim();
  else delete next.opening;
  if (draft.account.trim()) next.account = draft.account.trim();
  else delete next.account;
  return next;
}
