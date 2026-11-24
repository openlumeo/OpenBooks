# Community post drafts (not posted)

Rules: research 04 could not fetch Reddit rules (blocked). Every subreddit rule below is UNVERIFIED. Read each sidebar and its rules page before posting, check flair and self-promotion limits, and disclose affiliation in each post ("I work on this"). Post only from the owner's own account.

## 1. r/mcp

UNVERIFIED: self-promotion rules, flair requirement.

Title: Open-source MCP server that returns a bank statement as proven JSON, or a refusal

```text
I work on Open Books, an open-source MCP server (npm package @lumeo_hq/openbooks) that lets an agent check a financial file before it uses the numbers.

The rule: a file is released only if its own arithmetic proves it. For a bank statement that means opening + transactions = closing, and the running balance ties on every row. If the check fails or the layout is unknown, the tool returns a typed refusal with a reason code and no partial data.

Setup is one command (npx -y -p @lumeo_hq/openbooks openbooks-mcp) and a stdio config entry. The README has the JSON for Claude Desktop and Cursor style clients.

It is pre-release (v0.2 engine). Tests use synthetic fixtures, not real bank exports, so I have no accuracy number and I am not claiming one. Feedback welcome, especially on the refusal shape and on which tool names are clear.

Repo: https://github.com/Sagexd08/OpenBooks  Docs: https://openbooks.lumeo.co.in/docs/mcp
```

## 2. r/LocalLLaMA

UNVERIFIED: self-promotion rules, flair.

Title: Local-first bank statement checker: PDF and scan runs use a model on your machine

```text
I work on Open Books. The part that may interest this sub: the CLI runs on your machine, and PDF and image runs use a local model by default (you can pass --no-model to skip it). The model is a cross-check; it can add doubt but it cannot cause a release. A file is released only if its own arithmetic balances, otherwise you get a typed refusal.

    npm i -g @lumeo_hq/openbooks
    openbooks statement.csv --currency INR --opening 1000.00 --out out

Scans need the [scan] extra (OCR, PyTorch). The optional typed-head model checks a file's reading against its weights by hash, and a release names the exact weights it used.

Honest limits: pre-release, synthetic test data only, no accuracy benchmark on real statements yet. Input limits 2 GB per file, 64 MB for text formats.

Repo: https://github.com/Sagexd08/OpenBooks  Docs: https://openbooks.lumeo.co.in/docs
```

## 3. Accountants (plain language, privacy first)

Suggested subreddits (UNVERIFIED: whether each allows tool announcements). Check each rule first; r/Accounting and r/IndiaInvestments were named in research 01 and 04. Do not post in the private groups unless their rules allow it.

Title: A free, open-source tool that checks a bank statement before you trust the Excel

```text
I am building a small open-source tool and wanted accountants' view before I push it further.

It reads a bank statement (CSV, OFX, MT940, text PDFs, and scans with OCR) and gives you a JSON file only if the numbers add up: the opening balance plus the transactions must equal the closing balance, and each row's running balance must tie. If they do not, it tells you why and gives you nothing to import. That is the point: a wrong digit should stop the process, not slip into the ledger.

Privacy first:
- The command-line version runs on your computer. Your file is read on your machine.
- Please do not send real client statements to anyone to test. Use a sample, or a statement with names and account numbers removed.
- The hosted web workspace is a separate thing. Check its privacy and retention page before uploading anything real: [owner to insert the retention and storage statement from the live docs].

What it does not do yet:
- It has only been tested on synthetic files, so I cannot tell you how often it refuses a good statement on your bank's format. Refusals are expected for layouts it does not know.
- No Tally or GST export yet.

If you try it, I would like to know which bank layout was refused and the refusal code, with the personal details removed.

Docs: https://openbooks.lumeo.co.in/docs  Source: https://github.com/Sagexd08/OpenBooks
```

Note: the "No Tally or GST export yet" line is a claim about missing features. Confirm against the repo before posting, and delete it if a Tally or GST output exists. Research 05 (not read here) may contain more.
