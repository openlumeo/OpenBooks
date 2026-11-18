# @openbooks/statements

`runFile` / `runFiles` from [@openbooks/core](https://www.npmjs.com/package/@openbooks/core), restricted to the statements layouts
(`LAYOUTS`). A file that proves out under any other layout comes back as a refusal with code `UNKNOWN_LAYOUT` and
`restricted: true`. Detection and proof happen in the Python engine; nothing is re-implemented here.

```ts
import { runFile, LAYOUTS } from "@openbooks/statements";
```
