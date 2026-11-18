# openbooks-core package boundary

Status: **implemented (0.1.0, unreleased).** The contract, normalisation, gates, registry, `process`, the `.xlsx` front end,
the grader and the CLI live here. Parsers still ship in the `openbooks` meta distribution and register through entry points
until the statements, gateways and tax packages are split out.

```bash
pip install -e packages/py/openbooks-core             # only jsonschema is installed
python -m openbooks_core engine-info                  # version, contract version, installed layouts (JSON)
python -m openbooks_core run file.csv --machine       # JSON lines on stdout; exit 0 released, 1 refused, 2 usage, 3 engine fault
```

With no provider installed every known layout is refused with the package to install; nothing is ever released by guesswork.

## Responsibility

The core package owns the stable `openbooks.v1` contract and shared deterministic
pipeline primitives:

- schema version and JSON Schema validation;
- typed refusals and processing parameters;
- Decimal/date/currency normalisation and field evidence;
- input guard, decoding and canonical output construction;
- layout registry interfaces and core balance assertions;
- compatibility facade for the existing `openbooks` import namespace and CLI.

It must not own provider-specific parsers, model weights, training scripts, payout
matching policy, or the doctor command.

## Compatibility requirements

1. Existing `import openbooks.pipeline` users continue to work.
2. Existing `openbooks run | report | link | eval` commands retain their arguments,
   exit semantics and output paths.
3. A released document remains byte-for-byte schema-compatible with
   `openbooks.v1`; a refusal remains typed and contains no partial data.
4. Money remains `Decimal` end-to-end. No float conversion or silent rounding.
5. A missing parser package must cause a typed refusal / actionable install hint,
   never a fallback parser guess.
6. Detection precedence is preserved: Stripe, Razorpay, PayPal, Wise, 1099-B,
   26AS, AIS, FIRA, bank CSV, trial balance; statement-native OFX and MT940
   detection retains its existing precedence.
7. The weights/calibration integrity binding remains owned by the statements
   package when the model assets move there.

## Planned Python distribution

- Distribution: `openbooks-core`
- Import namespace: `openbooks_core`
- Python: `>=3.11`
- Shared dependencies: `jsonschema` (other dependencies should be added only
  where the core implementation actually imports them).

Parser distributions depend on core; core must never depend on parser
distributions. The future `openbooks` meta distribution preserves the current
`openbooks` import and console-script compatibility.

## Registry contract

A layout registration must include:

- stable layout id and explicit priority;
- header matcher / file detector;
- parser callable receiving the existing typed parameters;
- optional layout-specific assertion gate;
- owning distribution name for diagnostics when that distribution is absent.

Registry loading must be deterministic and must not swallow import or entry-point
errors as "unknown layout". Unknown layouts remain `UNKNOWN_LAYOUT`; a recognised
layout whose provider is not installed reports the provider package to install.

## Migration sequence

1. Add core package skeleton and registry contract tests.
2. Extract shared primitives without changing parser implementations.
3. Add compatibility shims under `openbooks` and retain the CLI entry point.
4. Move parsers one family at a time and register them through entry points.
5. Run all existing tests and package-isolated acceptance tests before removing
   any duplicated legacy implementation.

## Acceptance gates

- The existing full test suite remains green.
- A clean environment can install core and import its public API.
- Compatibility imports and CLI flags remain unchanged.
- Unknown layout, missing optional provider, schema-invalid output, date ambiguity,
  Decimal precision and failed balance checks all fail closed.
- A synthetic golden valid document releases and its tampered twin is refused.
