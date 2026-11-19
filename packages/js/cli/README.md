# openbooks

```bash
npm install -g @lumeo_hq/openbooks   # also installs the Python engine (pip install openbooks)
openbooks statement.csv --currency INR --opening 1000.00   # same as: openbooks run statement.csv ...
openbooks gateways stripe.csv              # only gateway layouts; anything else is refused
openbooks doctor
```

Commands: `run`, `statements run`, `gateways run`, `tax run`, `doctor`, `install-engine`, `engine-info`. Flags: `--currency --opening --account
--allow-derived-opening --date-order dmy|mdy --no-ocr --model --out <dir> --json --python <path> --timeout <ms>`.

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.
Needs the Python engine; this package does not parse documents itself. Installing this package fetches it with `pip install openbooks`
(Python 3.11+). Skip that with `--ignore-scripts` or `OPENBOOKS_SKIP_PYTHON=1`, and run `openbooks install-engine` (`--scan` for OCR) later.
If your system Python refuses global installs, create a `.venv` in your project and run `.venv/bin/pip install openbooks`; it is picked up automatically.
