# @lumeo_hq/openbooks-core

Typed access to the Open Books engine. Hand it a financial document; get back either a **released** `openbooks.v1` document
(every amount a decimal string, every field with its evidence) or a **refusal** with a typed code. Nothing is parsed in
JavaScript: this package runs the Python engine as a child process and validates what comes back against the same JSON Schema
the engine uses.

```bash
pip install openbooks            # the engine (Python 3.11+)
npm install @lumeo_hq/openbooks-core
```

```ts
import { runFile, EngineError } from "@lumeo_hq/openbooks-core";

try {
  const r = await runFile("statement.csv", { currency: "INR", opening: "1000.00" });
  if (r.kind === "released") {
    console.log(r.document.data.transactions[0]?.amount?.amount); // "5.00": a string, never a float
  } else {
    console.log(r.code, r.message); // e.g. BALANCE_MISMATCH: a valid outcome, not an exception
  }
} catch (e) {
  if (e instanceof EngineError) console.error(e.kind, e.message, e.hint); // the engine could not run: nothing is known about the file
}
```

A refusal is a **value**. An `EngineError` (no Python, engine not installed, version mismatch, crash, timeout, output that does
not match the contract) is thrown, so a broken installation can never be mistaken for a bad document.

Python is found from `options.python`, then `OPENBOOKS_PYTHON`, then `./.venv`, then the system Python. Run `npx @lumeo_hq/openbooks doctor`
to diagnose an installation. Money is never a JavaScript number: pass `opening` as a string.

Options: `currency`, `opening`, `account`, `allowDerivedOpening`, `dateOrder` (`"dmy" | "mdy"`), `ocr`, `model`, `runTimeoutMs`
(default 120000), `maxOutputBytes`, `signal`, `accept` (release only these layouts), `python`.
