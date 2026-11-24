# Open source release

The [repository license](../LICENSE.md) covers the Python engine, npm package, and three designated model files under Apache-2.0. Prepare the public repository from a fresh export of those files. The export includes public contribution policies, documentation and CI.

From the private checkout root, run these checks with Python 3.11+ and Git installed.

    python scripts/export_public.py ../openbooks-public --dry-run
    python scripts/export_npm.py ../openbooks-npm-public --dry-run

Remove --dry-run to write each tree into an empty directory. Stage any new source files you intend to include before exporting. The exporters use Git's index to select files and read their contents from the working tree.

## Verify the public source export

From the exported source tree, use a fresh virtual environment.

    python -m pip install -e packages/py/openbooks pytest hypothesis build
    python -m openbooks doctor
    python -m pytest packages/py/openbooks/tests tests/test_cli_machine.py tests/test_model_card.py
    python -m build --sdist --wheel packages/py/openbooks

In the same shell, install and test the JS workspace with Node.js and pnpm.

    pnpm --dir packages/js install --frozen-lockfile
    pnpm --dir packages/js --filter @lumeo_hq/openbooks check-generated
    pnpm --dir packages/js build
    pnpm --dir packages/js test

The npm publishing mirror builds from its own root with pnpm install --frozen-lockfile and pnpm build. Its publish workflow uses npm trusted publishing with provenance. Initialize each export as a fresh Git repository when preparing to publish.
