# dev.to article outline (draft, not published)

Working title: Verifying bank statements with an MCP server: released only if the arithmetic balances

Target: dev.to, with the canonical link to https://openbooks.lumeo.co.in/docs (tag and canonical rules UNVERIFIED in research 04; check dev.to before publishing). Length: about 900 to 1,200 words. Every code block is taken from the repo or from the commands in the CLI and Python READMEs.

## 1. Opening (about 80 words)

- The problem: an agent that reads a bank statement and reports totals can be wrong without noticing. A dropped row or a swapped sign shifts every later balance.
- The answer in one sentence: Open Books releases a file only if its own arithmetic proves it, otherwise it returns a typed refusal.
- State up front: v0.2 is pre-release and tested on synthetic fixtures.

## 2. The rule (about 150 words)

Source: `packages/py/openbooks/src/openbooks/core/gates.py` (gates per batch kind) and the root README "Why" section.

- `opening + sum(transactions) = closing`.
- The running balance ties on every row.
- At least one assertion must be independent evidence printed in the document.
- Refusal: no partial release, a typed code, exit code 1 from the CLI.

## 3. Run it from the command line (about 150 words)

Source: `packages/js/cli/README.md`, "Automate a run" and install block.

```bash
npm i -g @lumeo_hq/openbooks
openbooks statement.csv --currency INR --opening 1000.00 --out out
```

Show what the output directory contains: one `openbooks.v1` JSON per input file, named by the SHA-256 of the file (source: `packages/py/openbooks/README.md` "Use" section). Show the exit codes: 0 released, 1 refused, 2 usage error, 3 engine could not run.

## 4. Use it from Python (about 150 words)

Source: `packages/py/openbooks/README.md`.

```python
from decimal import Decimal
from pathlib import Path

from openbooks import Params, process

doc = process(Path("statement.csv"), Params(currency="INR", opening=Decimal("1000.00")))
print(doc["status"], doc.get("error"))
```

Explain that a refusal is a value, not an exception, and show the loop over `doc["data"]["transactions"]` for the released case (fields `date`, `direction`, `amount`).

## 5. Give an agent the same check over MCP (about 200 words)

Source: `packages/js/mcp/README.md`.

```bash
npx -y @lumeo_hq/openbooks-mcp
```

```json
{
  "mcpServers": {
    "openbooks": {
      "command": "npx",
      "args": ["-y", "@lumeo_hq/openbooks-mcp", "--root", "/path/to/financial/files"]
    }
  }
}
```

Explain `--root` and that omitting it uses synthetic samples and small in-memory uploads. Do not describe tool names beyond what the MCP README lists.

## 6. What it does not do (about 120 words)

Source: the Limitations sections of the root README and the Python package README.

- Synthetic-only evaluation so far. No accuracy number is claimed.
- Unknown layouts are refused, not guessed. Coverage is the list of layouts in the registry.
- PayPal, Wise and tax layouts are experimental.
- Limits: 2 GB per file, 64 MB for text formats (`packages/py/openbooks/src/openbooks/core/guard.py`).
- Scans need the `[scan]` extra for OCR.

## 7. Where to go next (about 40 words)

- Docs: https://openbooks.lumeo.co.in/docs
- Source: https://github.com/Sagexd08/OpenBooks
- Invite comments on refused files, with the bank and the refusal code, not the customer data.

## Before publishing (owner)

- Run each code block once on a clean machine and paste the real output. Do not paste output that was not produced.
- Remove any statement about users, customers, awards or accuracy.
- Do not include real bank statements in screenshots or examples.
