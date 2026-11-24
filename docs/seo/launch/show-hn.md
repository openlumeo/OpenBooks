# Show HN draft (not posted)

Rules verified in research 04 (https://news.ycombinator.com/showhn.html): the thing must be runnable by people on their own computer; the creator must stay in the thread; no sign-up gate; no landing page, newsletter or list as the Show HN target. Launch only when the owner can answer comments for several hours.

## Title (77 characters)

```
Show HN: Open Books - bank statements to JSON, refused if totals don't tie
```

## Link to submit

The GitHub repository, not the marketing site: https://github.com/Sagexd08/OpenBooks

## First comment (draft)

```text
Hi HN, I built Open Books, a CLI and Python package that turns a financial file into one JSON document, or refuses it with a reason code.

The rule it enforces: a file is released only if its own numbers prove themselves. For a bank statement that means opening + sum(transactions) = closing, the running balance ties on every row, and at least one check is independent evidence printed in the document, not the parser's own arithmetic. If a check fails or the layout is unknown, it writes a refusal and no partial result. Settlements and some tax layouts have their own checks.

Try it on your machine with no account:

    npm i -g @lumeo_hq/openbooks
    openbooks statement.csv --currency INR --opening 1000.00 --out out

Use a CSV from the repo's synthetic samples to start. The npm install also installs the Python engine (Python 3.11+). If the hook is skipped, run `openbooks install-engine --scan`. Exit code 0 means released, 1 means at least one refusal.

For agents there is an MCP server on npm, `@lumeo_hq/openbooks` (`npx -y -p @lumeo_hq/openbooks openbooks-mcp`).

Limits, stated plainly:
- Version 0.2 is pre-release. All fixtures and tests are synthetic. I have not measured accuracy on real bank exports, so I cannot give you an accuracy number.
- Only the layouts the registry knows are read. Unknown layouts are refused, not guessed. Bank coverage is whatever the layouts in the repo cover; see the docs.
- PayPal, Wise and the tax layouts are experimental.
- Input limits: 2 GB per file, 64 MB for text formats (CSV, OFX, QFX, STA, MT940, TXT).
- PDF and image runs use a model on your machine by default; pass --no-model to skip it. Scans need OCR (the [scan] extra).

Docs: https://openbooks.lumeo.co.in/docs. Source and issues: https://github.com/Sagexd08/OpenBooks/issues. I will answer questions here; if a layout is refused on your file, tell me the bank and I will look at the refusal code.
```

## Before posting (owner)

- Confirm the npm install and the CLI command run on a clean machine. This draft is not verified by a run.
- Confirm the sample CSV path in the repo and replace "a CSV from the repo's synthetic samples" with the exact path.
- Confirm the licence. The CLI and MCP npm packages are Apache-2.0.
- Delete any sentence you cannot back with the repo at the time of posting.
