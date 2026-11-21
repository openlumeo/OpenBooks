# @lumeo_hq/openbooks-tax

`runFile` / `runFiles` from [@lumeo_hq/openbooks-core](https://www.npmjs.com/package/@lumeo_hq/openbooks-core), restricted to the tax layouts
(`LAYOUTS`). A file that proves out under any other layout comes back as a refusal with code `UNKNOWN_LAYOUT` and
`restricted: true`. Detection and proof happen in the Python engine; nothing is re-implemented here.

```ts
import { runJobs } from "@lumeo_hq/openbooks-tax";

for await (const result of runJobs([
  { file: "form-26as.csv" },
  { file: "trial-balance.xlsx", options: { currency: "INR" } },
])) {
  console.log(result.file, result.kind);
}
```
Install Python 3.11+ and `python -m pip install openbooks`. Use `LAYOUTS` to inspect the supported Form 26AS, AIS, FIRA, Form 1099-B and trial-balance layout IDs. Keep source totals in exports and use one matching sheet per workbook. Handle refusals in a review queue and preserve each released document's evidence.

[Tax and workpaper workflow](https://openbooks.lumeo.co.in/docs/tax-and-workpapers)
