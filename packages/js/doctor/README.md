# @lumeo_hq/openbooks-doctor

`runDoctor()` checks Node, finds a Python with the Open Books engine, and runs the engine's own diagnostics (providers, model
integrity, a built-in proven-or-refused self-test). A missing Python or engine comes back as a failed check in the report,
not as an exception.

~~~ts
import { runDoctor } from "@lumeo_hq/openbooks-doctor";

const report = await runDoctor({
  python: process.env.OPENBOOKS_PYTHON,
  deep: false,
});

for (const check of report.checks) {
  console.log(check.id, check.status, check.detail, check.fix ?? "");
}
if (!report.ok) process.exitCode = 1;
~~~

Use `deep: true` when your runner needs to load the typed heads with the `scan` extra. Use `strict: true` to treat warnings as readiness failures. Keep the Python executable explicit in CI when multiple interpreters are available.

[Installation and diagnostics](https://openbooks.lumeo.co.in/docs/installation)
