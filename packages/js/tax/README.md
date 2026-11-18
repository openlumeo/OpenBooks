# @lumeo_hq/openbooks-tax

`runFile` / `runFiles` from [@lumeo_hq/openbooks-core](https://www.npmjs.com/package/@lumeo_hq/openbooks-core), restricted to the tax layouts
(`LAYOUTS`). A file that proves out under any other layout comes back as a refusal with code `UNKNOWN_LAYOUT` and
`restricted: true`. Detection and proof happen in the Python engine; nothing is re-implemented here.

```ts
import { runFile, LAYOUTS } from "@lumeo_hq/openbooks-tax";
```
