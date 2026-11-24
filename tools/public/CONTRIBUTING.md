# Contributing to Open Books

Use Python 3.11 or newer. For the JavaScript workspace, use Node.js 20 or newer and pnpm 10. Create and activate a virtual environment before installing the engine.

    python -m pip install -e packages/py/openbooks pytest hypothesis
    python -m openbooks doctor
    python -m pytest packages/py/openbooks/tests tests/test_cli_machine.py tests/test_model_card.py

For the CLI, library or MCP server, run the following from the checkout root in the same environment.

    pnpm --dir packages/js install --frozen-lockfile
    pnpm --dir packages/js --filter @lumeo_hq/openbooks check-generated
    pnpm --dir packages/js build
    pnpm --dir packages/js test

When changing the output contract, edit the JSON Schema under packages/py/openbooks/src/openbooks/core/schema. Run pnpm --dir packages/js sync-schema and pnpm --dir packages/js generate to update the JavaScript copies and types.

A new layout needs a parser, a gate that proves the result using evidence printed in the document, and a tampered fixture that the gate refuses. Describe which layouts were tested on real exports. Use synthetic documents in tests and reports.

Sign off each commit with git commit -s to certify the [Developer Certificate of Origin](https://developercertificate.org/). See the [security policy](SECURITY.md) for private reporting.
