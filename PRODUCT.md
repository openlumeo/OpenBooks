# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Next.js (App Router) with TypeScript for the web app. The backend is a FastAPI service wrapping the Python engine (`openbooks.pipeline.process`, `openbooks.link.link`), reached only through Next.js route handlers. Q&A calls an open-weights model through an OpenAI-compatible API (OpenRouter by default) from the Next.js server. Full design: `docs/web/design.md`.

## Users

Primary: chartered accountants and bookkeepers in India who process many clients' financial documents (bank statements, payment-gateway settlements, Form 26AS, AIS, FIRA, trial balances, Excel workpapers). Their job is to turn a client's pile of files into figures they can post to the books and defend under review, without retyping and without trusting a number they cannot trace back to the source.

## Product Purpose

Open Books turns each financial file into one proven `openbooks.v1` JSON document, or a typed refusal. A file is released only when its own arithmetic proves it: opening + transactions = closing, running balances tie, settlement gross − fees − tax = net, and printed totals match. At least one check must be independent evidence printed in the document. Every field carries its evidence (page, bbox, row, raw text, method).

The web app is a conversation-style workspace. The user drops files into a thread, gets one released document or refusal per file with the proof visible, then asks questions about the released documents in plain language. Success means the accountant trusts a released file enough to use it, and understands a refused file well enough to fix the input (for example by supplying the opening balance) or to set it aside.

## Positioning

Proven or refused, never guessed. Other extraction tools return their best reading with a confidence score. Open Books releases a file only when the document's own numbers tie out, and otherwise returns a typed refusal with no partial output. Optional ML heads can only add doubt (`LOW_CONFIDENCE`); they can never cause a release. In the Q&A, the model never does arithmetic itself: totals and counts come from code over the released data, with file and record ids cited.

## Operating Context

- Accountants work through batches of client files, often at month-end or tax-filing time. A thread holds one batch.
- Inputs: bank CSV, OFX/QFX, MT940, bank-statement PDFs and scans (text layer or OCR), Wise statements, Stripe balance exports, Razorpay settlements, PayPal activity, Form 26AS (TDS), AIS, FIRA, Form 1099-B, trial balances, `.xlsx` workpapers. Limit 20 MB per file.
- Cross-file linking matches gateway payouts and FIRA remittances to the bank credits that received them. A match needs exactly equal amounts and dates within a window; ties are reported as ambiguous, not resolved.
- Hosted by Lumeo: users upload files to a Lumeo-run service. Files are processed in memory and not stored server-side; thread history lives in the user's browser.

## Capabilities and Constraints

- Six refusal codes, shown verbatim with the engine's message: `UNKNOWN_LAYOUT`, `UNSUPPORTED_INPUT`, `PARSE_ERROR`, `BALANCE_MISMATCH`, `LOW_CONFIDENCE`, `OUTPUT_INVALID`.
- Output is always one JSON per input file; the app never merges, edits or "fixes" engine output.
- Money is Decimal end to end; the UI must never round, reformat away precision, or compute totals in floating point.
- PayPal activity, Wise statement and Form 1099-B layouts are built but follow public descriptions of those exports and are tested on synthetic files only; present them as unverified. Other 1099 forms are not parsed.
- Numeric dates: the day/month order is proven from the file; bank statements (CSV and PDF) default to day-first without proof, PayPal and 1099-B refuse rather than guess. The user can supply the order.
- Python packages provide the engine and format providers. The npm packages provide typed wrappers that run the Python engine locally.
- Open decision: authentication and account model for the hosted service. The v1 spec has no accounts; a hosted deployment will need them before real client data is accepted.
- Open decision: data-processing terms and retention statement for hosted uploads (financial data of the accountant's clients).

## Brand Commitments

- Name: "Open Books", presented as a Lumeo product ("Open Books by Lumeo").
- The visual language is binding: Lumeo's design system, `d:\Code\Lumeo\Lumeo_Pay-Prototype-\DESIGN.md`, with tokens from `frontend/web/app/(marketing)/globals.css` in that repo. Brand assets (Lumeo mark and lockup, light and dark cuts) are in `frontend/web/public/brand/` there. The Lumeo wordmark artwork is never redrawn in a webfont.
- Voice follows the engine's docs: plain, exact, no hype. A refusal is stated as a fact with its reason, never softened or apologised away.

## Evidence on Hand

- Pipeline diagram: `docs/pipeline.jpeg`.
- Measured results, synthetic data only: `docs/evidence/*.json` (for example 27/27 expected-ok files released, 0 false accepts, 0 schema violations over 69 synthetic end-to-end cases).
- Synthetic golden set: `openbooks.golden.build()` writes balanced files plus tampered twins that must be refused. This is suitable for in-app samples.
- Absent, and must not be fabricated: real-world accuracy figures, customer names, testimonials, firm logos, compliance certifications, pricing. No real statements have been scored.

## Product Principles

1. **Proof before data.** A figure is shown as usable only when its file was released; the checks that released it are one click away.
2. **A refusal is an answer.** It names the stage, the code and the engine's reason, and when the fix is known (a missing opening balance or currency) it offers that fix directly.
3. **Traceable to the source.** Every released value can be followed to its page, box, row and raw text.
4. **Honest about maturity.** The app states plainly, in the app itself, that this is an early release tested on synthetic data.
5. **The model explains, code counts.** Language-model answers cite records, and numbers come from deterministic code.

## Accessibility & Inclusion

Contrast follows the Lumeo pairs verified to WCAG AA in DESIGN.md. Long-running work (OCR, multi-file runs) must show progress that also works with reduced motion. Data tables must remain usable with a keyboard and a screen reader, since accountants live in them.
