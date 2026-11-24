# Contributing

Thanks for helping. The one rule that outranks the rest: **never weaken a financial check to make something pass.** A change that
lets a tampered document through, guesses an ambiguous date, or turns a refusal into a release will not be merged.

## Sign-off
Contributions are accepted under the repository licence, certified with the [Developer Certificate of Origin](https://developercertificate.org/):
add `Signed-off-by: Your Name <you@example.com>` to each commit (`git commit -s`).

## Before you open a pull request
- Python: install the packages editable (see the README), then run `pytest packages/py/*/tests tests`.
- JS: `cd packages/js && pnpm install && pnpm --filter @lumeo_hq/openbooks run check-generated && pnpm exec tsc -b && pnpm exec vitest run`.
- Changing the output contract: edit the schema under `packages/py/openbooks/src/openbooks/core/schema/`, then run `pnpm sync-schema && pnpm generate`. CI fails if the generated TypeScript is stale.
- A new layout needs: a parser, a gate that proves it from the document's own numbers, a tampered fixture that must be refused, and a statement of whether it has been checked against a real export (it is experimental until it has).
- Never commit real client documents or real account numbers, including redacted ones you are not sure about.
