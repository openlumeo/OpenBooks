# @openbooks/doctor

`runDoctor()` checks Node, finds a Python with the Open Books engine, and runs the engine's own diagnostics (providers, model
integrity, a built-in proven-or-refused self-test). A missing Python or engine comes back as a failed check in the report,
not as an exception.
