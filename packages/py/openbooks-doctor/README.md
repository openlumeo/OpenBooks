# openbooks-doctor

```bash
pip install openbooks-doctor
openbooks doctor            # or: python -m openbooks_doctor
openbooks doctor --json     # machine-readable, schema "openbooks.doctor.v1"
openbooks doctor --deep     # also imports PyTorch and loads the model
openbooks doctor --strict   # warnings fail too
```

Checks: Python version; core and its schemas; provider versions in step with core; every installed provider actually imports;
which known layouts have no provider (and the package to install); PyMuPDF and the OCR dependencies; model weights match their
calibration by sha256; a built-in self-test per installed layout (a balanced document must release and its tampered twin must
be refused, and a released tampered document is reported as a false accept); temp directory and free space.

Exit codes: `0` nothing failed (warnings allowed unless `--strict`), `1` a check failed, `2` usage error, `3` doctor itself crashed.
Doctor reads no user documents and prints no document content.
