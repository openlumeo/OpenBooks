---
description: Verify a financial document with Open Books
argument-hint: <relative-path> [opening-balance]
---

Verify the document at `$ARGUMENTS` with the Open Books `execute` tool. Use one `process_file` step (or `process_upload` if no `--root` folder is set), then a `records` step for transactions. Supply the opening balance only if the user gave it or it comes from a trusted source. If the status is `refused`, report the code and what to check, and stop. Never present a refused document as verified.
