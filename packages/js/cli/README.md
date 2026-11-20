# openbooks

```bash
npm install -g @lumeo_hq/openbooks   # also installs the Python engine with OCR and model support
openbooks statement.csv --currency INR --opening 1000.00   # same as: openbooks run statement.csv ...
openbooks gateways stripe.csv              # only gateway layouts; anything else is refused
openbooks doctor
```

Commands: `run`, `statements run`, `gateways run`, `tax run`, `doctor`, `install-engine`, `engine-info`. Flags: `--currency --opening --account
--allow-derived-opening --date-order dmy|mdy --no-ocr --no-model --out <dir> --json --python <path> --timeout <ms>`.

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.
PDF and image runs use the model on your machine by default. Pass `--no-model` to skip the cross-check.
The npm install hook fetches `openbooks[scan]` 0.2.x for Python 3.11+, including PyTorch. If your package manager skips the hook or you set `OPENBOOKS_SKIP_PYTHON=1`, run `openbooks install-engine --scan`.
If your system Python refuses global installs, create a `.venv` in your project and run `openbooks install-engine --scan` from that directory.
