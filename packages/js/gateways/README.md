# @lumeo_hq/openbooks-gateways

`runFile` / `runFiles` from [@lumeo_hq/openbooks-core](https://www.npmjs.com/package/@lumeo_hq/openbooks-core), restricted to the gateways layouts
(`LAYOUTS`). A file that proves out under any other layout comes back as a refusal with code `UNKNOWN_LAYOUT` and
`restricted: true`. Detection and proof happen in the Python engine; nothing is re-implemented here.

```ts
import { runFile } from "@lumeo_hq/openbooks-gateways";

const result = await runFile("stripe-balance.csv");
if (result.kind === "released") {
  console.log(result.document.data.batches, result.document.assertions);
} else {
  console.warn(result.code, result.message);
}
```
Install Python 3.11+ and `python -m pip install openbooks`. Use `runFiles` for a batch with shared settings or `runJobs` to set currency and date order per export. The gateway layouts include Stripe, Razorpay, PayPal and Wise. Review the payout assertion and use exact decimal values when reconciling with bank credits. PayPal and Wise layouts have synthetic test coverage.

[Settlement reconciliation workflow](https://openbooks.lumeo.co.in/docs/payment-settlements)
