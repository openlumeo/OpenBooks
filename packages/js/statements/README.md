# @lumeo_hq/openbooks-statements

`runFile` / `runFiles` from [@lumeo_hq/openbooks-core](https://www.npmjs.com/package/@lumeo_hq/openbooks-core), restricted to the statements layouts
(`LAYOUTS`). A file that proves out under any other layout comes back as a refusal with code `UNKNOWN_LAYOUT` and
`restricted: true`. Detection and proof happen in the Python engine; nothing is re-implemented here.

```ts
import { runJobs } from "@lumeo_hq/openbooks-statements";

for await (const result of runJobs([
  { file: "bank.csv", options: { currency: "INR", opening: "1000.00" } },
  { file: "bank.ofx", options: { opening: "531.27" } },
])) {
  console.log(result.kind === "released" ? result.document.data.batches : result.code);
}
```
Install Python 3.11+ and `python -m pip install openbooks` before running the Node.js package. Supply a verified opening balance when the export lacks one. Use `dateOrder` for ambiguous numeric dates. PDF and image runs use the model by default. Install `openbooks[scan]` for OCR and model capabilities. Set `model: false` to read a text-layer PDF with the base engine.

[Bank statement workflow](https://openbooks.lumeo.co.in/docs/bank-statements) · [PDF and OCR](https://openbooks.lumeo.co.in/docs/pdf-and-ocr)
