# Contributing to Open Books

The Python engine and npm package accept contributions under Apache-2.0. The [public contribution guide](tools/public/CONTRIBUTING.md) describes sign-off, parser requirements and test data. The [release guide](docs/OPEN_SOURCE.md) describes how to prepare a public checkout.

## Set up the workspace

Use Python 3.11 or newer. For the JavaScript workspace and web app, use Node.js 22.12 or newer and pnpm 10.

    python -m venv .venv

Activate the environment with .venv\Scripts\Activate.ps1 on PowerShell or source .venv/bin/activate on macOS or Linux. Then install the editable packages from the repository root.

    python -m pip install -e packages/py/openbooks -e packages/py/openbooks-lab -e "server[test]" hypothesis build
    python -m openbooks doctor

Install -e "packages/py/openbooks[scan]" when working on image OCR or the typed model.

## Check your changes

Run the relevant checks from the repository root.

| Area | Files | Commands |
| --- | --- | --- |
| Python engine and service | packages/py/openbooks/, server/ | python -m pytest tests packages/py/openbooks/tests server/tests |
| JS CLI, API and MCP server | packages/js/cli/ | pnpm --dir packages/js install --frozen-lockfile, pnpm --dir packages/js build, pnpm --dir packages/js test |
| Web workspace and site | web/app/, web/components/, web/lib/ | pnpm --dir web install --frozen-lockfile, pnpm --dir web typecheck, pnpm --dir web test, pnpm --dir web build |
| Agent kit | harness/ | Follow the [agent kit guide](harness/README.md) |

See the [release guide](docs/OPEN_SOURCE.md) for packaging checks.
