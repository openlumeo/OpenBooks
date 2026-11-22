import { describe, expect, it } from "vitest";
import {
  composerHint,
  fileExtension,
  isImageName,
  isOverLimit,
  MAX_FILES,
  problemsFor,
  type Pending,
} from "@/components/composer-parts/problems";
import { draftError, draftToParams, isCurrencyInvalid, isOpeningInvalid } from "@/components/composer-parts/params-draft";
import { HISTORY_MESSAGES, priorExchanges, threadDocs, titleFor, trimHistory } from "@/lib/workspace/history";
import type { EngineDoc, RunParams, Thread, Turn } from "@/lib/types";

const MB = 1024 * 1024;
const pendingFile = (name: string, size = 10, id = name): Pending => ({ id, file: new File(["x".repeat(size)], name) });
const ALLOWED = [".csv", ".pdf"];

describe("titleFor", () => {
  it("uses the file name for one file and a count for several", () => {
    expect(titleFor([new File(["a"], "jan.csv")], "")).toBe("jan.csv");
    expect(titleFor([new File(["a"], "jan.csv"), new File(["b"], "feb.csv"), new File(["c"], "x.pdf")], "")).toBe("jan.csv + 2 more");
  });

  it("collapses whitespace and truncates long questions with an ellipsis", () => {
    expect(titleFor([], "  why   is\n\tthis  ")).toBe("why is this");
    const long = "a".repeat(100);
    const title = titleFor([], long);
    expect(title).toHaveLength(58);
    expect(title.endsWith("…")).toBe(true);
  });

  it("falls back to a fixed title for blank input and keeps unicode intact", () => {
    expect(titleFor([], "   ")).toBe("Untitled run");
    expect(titleFor([], "支払い ₹")).toBe("支払い ₹");
  });
});

describe("threadDocs", () => {
  it("returns nothing for a missing thread or a thread with no released files", () => {
    expect(threadDocs(undefined)).toEqual([]);
    expect(threadDocs(thread([]))).toEqual([]);
  });

  it("lists only files that have a document, in turn order", () => {
    const docs = threadDocs(thread([
      run([{ name: "a.csv", doc: doc("A") }, { name: "b.csv" }]),
      run([{ name: "c.csv", doc: doc("C") }]),
    ]));
    expect(docs.map((d) => d.doc)).toEqual([doc("A"), doc("C")]);
    expect(docs).toHaveLength(2);
  });
});

describe("priorExchanges", () => {
  it("pairs a question with the answer that followed it, when the answer is complete", () => {
    const history = priorExchanges(thread([
      ask("q1"), answer("a1"),
    ]));
    expect(history).toEqual([{ role: "user", content: "q1" }, { role: "assistant", content: "a1" }]);
  });

  it("skips streaming, failed, empty and unanswered exchanges", () => {
    const history = priorExchanges(thread([
      ask("streaming"), answer("partial", "streaming"),
      ask("failed"), answer("oops", "done", "boom"),
      ask("blank"), answer("   "),
      ask("unanswered"),
      ask("good"), answer("ok"),
    ]));
    expect(history).toEqual([{ role: "user", content: "good" }, { role: "assistant", content: "ok" }]);
  });

  it("returns nothing for a missing thread and keeps unicode content", () => {
    expect(priorExchanges(undefined)).toEqual([]);
    expect(priorExchanges(thread([ask("支払いはいくら"), answer("₹100")]))[1]).toEqual({ role: "assistant", content: "₹100" });
  });
});

describe("trimHistory", () => {
  it("keeps short histories unchanged", () => {
    const h = [{ role: "user" as const, content: "q" }, { role: "assistant" as const, content: "a" }];
    expect(trimHistory(h)).toEqual(h);
  });

  it("keeps only the newest messages and starts on a user message", () => {
    const long = Array.from({ length: HISTORY_MESSAGES + 3 }, (_, i) => ({
      role: (i % 2 === 0 ? "user" : "assistant") as "user" | "assistant",
      content: `m${i}`,
    }));
    const trimmed = trimHistory(long);
    expect(trimmed.length).toBeLessThanOrEqual(HISTORY_MESSAGES);
    expect(trimmed[0]!.role).toBe("user");
    expect(trimmed.at(-1)).toEqual(long.at(-1));
  });

  it("returns an empty list when nothing starts with a user message", () => {
    expect(trimHistory([{ role: "assistant", content: "orphan" }])).toEqual([]);
    expect(trimHistory([])).toEqual([]);
  });
});

describe("file classification", () => {
  it("normalises extensions to lower case and returns empty for names without one", () => {
    expect(fileExtension("STATEMENT.CSV")).toBe(".csv");
    expect(fileExtension("README")).toBe("");
    expect(fileExtension("archive.tar.gz")).toBe(".gz");
  });

  it("recognises image names case-insensitively and nothing else", () => {
    expect(isImageName("scan.PNG")).toBe(true);
    expect(isImageName("photo.jpeg")).toBe(true);
    expect(isImageName("statement.pdf")).toBe(false);
    expect(isImageName("pngfile")).toBe(false);
  });

  it("marks a file over the size limit or of an unsupported type", () => {
    expect(isOverLimit(pendingFile("a.csv", 11), ALLOWED, 10)).toBe(true);
    expect(isOverLimit(pendingFile("a.exe", 1), ALLOWED, 10)).toBe(true);
    expect(isOverLimit(pendingFile("a.csv", 10), ALLOWED, 10)).toBe(false);
  });

  it("accepts any type when no types are listed", () => {
    expect(isOverLimit(pendingFile("a.exe", 1), [], 10)).toBe(false);
  });
});

describe("problemsFor", () => {
  it("returns null for an acceptable batch, including an empty one", () => {
    expect(problemsFor([pendingFile("a.csv")], ALLOWED, MB)).toBeNull();
    expect(problemsFor([], ALLOWED, MB)).toBeNull();
  });

  it("reports the number of files to remove when there are too many", () => {
    const many = Array.from({ length: MAX_FILES + 3 }, (_, i) => pendingFile("a.csv", 1, `id${i}`));
    expect(problemsFor(many, ALLOWED, MB)).toBe(`At most ${MAX_FILES} files per run. Remove 3.`);
  });

  it("names the first unsupported file and lists what is accepted", () => {
    expect(problemsFor([pendingFile("ok.csv"), pendingFile("bad.exe"), pendingFile("worse.zip")], ALLOWED, MB))
      .toBe("bad.exe is not a supported type. Accepted: .csv .pdf.");
  });

  it("names the first file over the size limit", () => {
    expect(problemsFor([pendingFile("big.csv", 2 * MB)], ALLOWED, MB)).toBe("big.csv is over the 1.0 MB limit.");
  });

  it("checks the file count before types and sizes", () => {
    const many = Array.from({ length: MAX_FILES + 1 }, (_, i) => pendingFile("bad.exe", 1, `id${i}`));
    expect(problemsFor(many, ALLOWED, MB)).toMatch(/^At most/);
  });
});

describe("composerHint", () => {
  const base = {
    operation: null, engineUp: true, problem: null, hasFiles: false, hasImage: false,
    hasText: false, hasDocs: false, askEnabled: true,
  } as const;

  it("reports the current operation before anything else", () => {
    expect(composerHint({ ...base, operation: "link", problem: "x" })).toBe("Checking links across released files.");
    expect(composerHint({ ...base, operation: "history", engineUp: false })).toBe("Updating browser history.");
  });

  it("reports an unreachable engine before a file problem", () => {
    expect(composerHint({ ...base, engineUp: false, problem: "bad" })).toBe("The engine is not reachable, so files cannot be checked right now.");
  });

  it("shows a file problem, then the OCR issue only for image files", () => {
    expect(composerHint({ ...base, problem: "too big", hasFiles: true })).toBe("too big");
    expect(composerHint({ ...base, hasFiles: true, ocrIssue: "no OCR" })).toBe("Each file is checked on its own. Nothing is released unless its numbers tie out.");
    expect(composerHint({ ...base, hasFiles: true, hasImage: true, ocrIssue: "no OCR" })).toBe("no OCR");
  });

  it("explains missing LLM configuration only when a question could be asked", () => {
    const off = { ...base, askEnabled: false as const };
    expect(composerHint({ ...off, hasText: true })).toContain("OPENBOOKS_LLM_API_KEY");
    expect(composerHint({ ...off, hasDocs: true })).toContain("OPENBOOKS_LLM_API_KEY");
    expect(composerHint(off)).toBe("Attach files to begin");
  });

  it("gives the keyboard hint when questions are enabled and the composer is idle", () => {
    expect(composerHint(base)).toBe("Enter to send · Shift+Enter for a new line");
    expect(composerHint({ ...base, askEnabled: null })).toBe("Attach files to begin");
  });
});

describe("params draft", () => {
  const empty = { currency: "", opening: "", account: "" };

  it("flags a currency that is not three letters, and an opening that is not a plain number", () => {
    expect(isCurrencyInvalid("IN")).toBe(true);
    expect(isCurrencyInvalid("")).toBe(false);
    expect(isCurrencyInvalid(" inr ")).toBe(false);
    expect(isOpeningInvalid("1,000.00")).toBe(false);
    expect(isOpeningInvalid("1e3")).toBe(true);
    expect(isOpeningInvalid("-12.5")).toBe(false);
    expect(isOpeningInvalid(",")).toBe(true);
  });

  it("reports the currency error before the opening error, and nothing for a valid draft", () => {
    expect(draftError({ ...empty, currency: "X", opening: "bad" })).toBe("Currency must be three letters, like INR.");
    expect(draftError({ ...empty, opening: "bad" })).toBe("Opening balance must be a plain number, like 1000.00.");
    expect(draftError(empty)).toBeNull();
  });

  it("uppercases the currency, strips thousands separators and trims the account", () => {
    const next = draftToParams({}, { currency: " inr ", opening: "1,000.50", account: "  Main  " });
    expect(next).toEqual({ currency: "INR", opening: "1000.50", account: "Main" });
  });

  it("removes blank fields rather than sending empty strings, and keeps unrelated params", () => {
    const current: RunParams = { currency: "USD", opening: "5.00", account: "old", date_order: "mdy" };
    expect(draftToParams(current, empty)).toEqual({ date_order: "mdy" });
  });

  it("does not mutate the params it was given", () => {
    const current: RunParams = { currency: "USD" };
    draftToParams(current, empty);
    expect(current).toEqual({ currency: "USD" });
  });
});


function thread(turns: Turn[]): Thread {
  return { id: "t", title: "t", createdAt: 0, updatedAt: 0, turns };
}

function run(files: { name: string; doc?: EngineDoc }[]): Turn {
  return {
    id: `run-${files.map((f) => f.name).join("-")}`, kind: "run", at: 0, sourceTurnId: "u", state: "done",
    files: files.map((f, index) => ({ index, name: f.name, size: 1, stages: [], state: "done", params: {}, doc: f.doc })),
  } as unknown as Turn;
}

function ask(text: string): Turn {
  return { id: `ask-${text}`, kind: "user-ask", at: 0, text } as unknown as Turn;
}

function answer(text: string, state: "done" | "streaming" = "done", error?: string): Turn {
  return { id: `ans-${text}`, kind: "answer", at: 0, text, tools: [], state, error } as unknown as Turn;
}

function doc(label: string): EngineDoc {
  return { status: "ok", label } as unknown as EngineDoc;
}
