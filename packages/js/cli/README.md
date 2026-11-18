# openbooks

```bash
pip install openbooks && npm install -g @lumeo_hq/openbooks
openbooks run statement.csv --currency INR --opening 1000.00
openbooks gateways run stripe.csv          # only gateway layouts; anything else is refused
openbooks doctor
```

Commands: `run`, `statements run`, `gateways run`, `tax run`, `doctor`, `engine-info`. Flags: `--currency --opening --account
--allow-derived-opening --date-order dmy|mdy --no-ocr --model --out <dir> --json --python <path> --timeout <ms>`.

Exit codes: `0` everything released, `1` something was refused, `2` usage error, `3` the engine could not run.
Needs the Python engine; this package does not parse documents itself.
