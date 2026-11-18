# openbooks-gateways

Providers for payment gateway exports, registered with `openbooks-core`:

| Layout | Gate | Status |
|---|---|---|
| `stripe_balance.v1` | settlement: gross - fee - tax = net per row, totals, payout | synthetic fixtures only |
| `razorpay_settlement.v1` | same | synthetic fixtures only |
| `paypal_activity.v1` | same (PayPal's own gross, fee and net columns) | **experimental**: public description, no real file seen |
| `wise_statement.v1` | statement: running balance ties on every row | **experimental**: public description, no real file seen |

```bash
pip install openbooks-gateways      # brings openbooks-core
python -m openbooks_core run stripe.csv --machine
```

Depends only on `openbooks-core`. Payout-to-bank-credit matching is not part of this package.
Numeric dates: Wise defaults to day-first; PayPal has no safe default, so the order must be provable from the file or given with `--date-order`.
