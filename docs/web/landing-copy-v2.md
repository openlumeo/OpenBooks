# Landing copy v2 (frozen script)

Direction: institutional, exact, unhurried. The page changes one belief: **confidence is not evidence.** Every other extraction tool returns its best reading and a score. Open Books returns a proof or a reason. The reader should finish thinking "I have been checking the wrong 3%."

Rules for every line:
- Say what the product does, in the order an accountant would verify it. No hype words: seamless, powerful, effortless, revolutionary, AI-powered, supercharge, unlock.
- No em dashes, no exclamation marks, no rhetorical question headlines.
- No "synthetic", "early release", "tested on synthetic data" banners, badges or captions anywhere on the landing page. (Decision by the owner: visitors already know.) Two basis lines are kept because a figure must state its basis: the Results caption and the Preview tag below.
- Numbers in copy come only from verified data constants. Never write a figure that is not in a `*-data.ts` file or the evidence JSON.
- Sentences short. Headings are statements, not labels. Body max 2 sentences per paragraph.

## 1. Hero
- H1: `Every figure proven, or refused with a reason.`
- Lede: `Open Books reads bank statements, payment settlements and tax records, then checks each document's own arithmetic. If it ties out, you get structured data with the source of every figure. If it does not, you get the reason, never a guess.`
- Primary CTA: `Open workspace`  Secondary: `Read the docs`
- Under CTAs (small, mono): `ONE FILE IN · ONE PROOF OUT` (replaces the maturity line; delete the maturity line)
- Proof pair labels: `Released` / `Refused`; file labels: `statement.csv` / `statement.csv, one balance altered`. Remove SYNTHETIC wording from any label.

## 2. Reframe (new section, id "reframe")
- Heading: `Confidence is not evidence.`
- Left column, mono label `A TYPICAL EXTRACTION TOOL`: `Returns its best reading. Attaches a score. Leaves you to check the rest.` Visual: a row of figures each tagged 97%, 94%, 99%, 88%.
- Right column, mono label `OPEN BOOKS`: `Returns a proven document, or a refusal. Nothing in between.` Visual: the same figures, tied out, each with a mint hairline.
- Closing line: `A figure at 97% still sends you back to the other 3%. Open Books does not score a document. It checks it.`

## 3. How a file is proven (id "how-proven")
- Heading: `Four checks stand between a file and your books.`
- Stage lines (use STAGES from web/lib/stages.ts for labels; these are the descriptions):
  - Detect: `Identifies the layout from the file itself. An unknown layout stops here.`
  - Parse: `Reads every row with its page, box and raw text.`
  - Normalise: `Puts dates, amounts and directions into one schema.`
  - Balance: `Opening plus transactions equals closing. Running balances tie on every row. Printed totals match.`
- Under the rail: `At least one check must be evidence printed in the document, not computed from our own output.`
- Footnote: `Optional model checks can only add doubt. They can never cause a release.`

## 4. Refusals (id "refusals")
- Heading: `When it cannot prove a file, it says so.`
- Body: `A refusal names the stage, the code and the engine's own reason. There is no partial output to second-guess, and where the fix is known, such as a missing opening balance, the workspace offers it inline.`
- Keep the table of six codes (Code, Stops at, Meaning) and the real engine message panel. Panel caption: `Engine output, unedited.`

## 5. Trace (id "trace")
- Heading: `Every figure leads back to its source.`
- Body: `Each value carries its page, box, row, raw text and extraction method. Review a figure the way you would review a voucher: by looking at the original.`
- Remove the `SYNTHETIC SAMPLE` tag; label the panel `EVIDENCE · txn-00001`.

## 6. Inputs (id "inputs")
- Heading: `The files your clients actually send.`
- Body: `Bank statements, gateway settlements, tax records and workpapers, in the formats they arrive in. Up to 20 MB per file.`
- Tag text for PayPal activity, Wise statement and Form 1099-B: `PREVIEW` with the note `Built to the published export format. Not yet validated on files from the wild.` (replaces UNVERIFIED and the synthetic wording).
- Keep the day-first note: `Day-first dates are assumed for bank statements; you can set the order per file.`

## 7. Ask (id "ask")
- Heading: `Ask in plain language. The totals come from code.`
- Body: `The model explains and cites. Every sum and count is computed over the released data with exact decimals, and every answer names the file and the record.`
- Remove the `EXAMPLE` tag wording only if the panel is clearly a conversation; otherwise keep `EXAMPLE` (it is not about synthetic data).

## 8. Results (id "measured")
- Heading: `What the engine has been held to.`
- Rows unchanged (69 end-to-end cases, 27 released, 0 false accepts, 0 schema violations). Add a fifth row only if verified in the evidence JSON.
- Caption (the one basis line): `Results from the engine's end-to-end test suite. See the evidence in the documentation.` (link to /docs/model)

## 9. Final CTA (id "start")
- Heading: `Bring one client's month-end. See what ties out.`
- Body: `Open the workspace, drop a file, and watch it released or refused with the reason on the page.`
- Buttons as before. Delete the maturity line under them.

## 10. Footer
- Statement (keep verbatim): `Files are processed in memory and not stored on the server. Thread history stays in your browser.`
- Replace the maturity link with a plain link `Model and limits` to `/docs/model`. Keep Docs, Workspace, `Docs for AI agents`.

## Nav
- `Docs`, `Open workspace`. Unchanged.
