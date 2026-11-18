# Licensing of this repository

This is Lumeo's private repository. It contains two kinds of material.

**Open packages: Apache License 2.0.** Everything under these directories is licensed under the Apache License, Version 2.0
(the `LICENSE` file in each directory is the licence text):

- `packages/py/openbooks-core`, `openbooks-gateways`, `openbooks-tax`, `openbooks-statements`, `openbooks-doctor`, `openbooks`
- `packages/js/*`
- the model files `models/roles_head.pt`, `models/roles_calibration.json` and `models/roles_model_card.json`

**Everything else is proprietary to Lumeo, all rights reserved**: `server/`, `web/`, `packages/py/openbooks-lab/`, `scripts/`,
`docs/`, `tests/` outside the open packages, the rest of `models/`, and this repository's history. Being able to read it here
grants no licence to use, copy or publish it.

`scripts/export_public.py` builds the public repository from the open packages only.
