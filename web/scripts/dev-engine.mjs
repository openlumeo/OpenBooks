import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const root = new URL("../../", import.meta.url);
const venvPython = fileURLToPath(new URL(
  process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python",
  root,
));
const python = existsSync(venvPython) ? venvPython : "python";
const engine = spawn(python, [
  "-m", "uvicorn", "openbooks_server.app:app", "--host", "127.0.0.1", "--port", "8765",
], { cwd: root, stdio: "inherit" });

engine.on("error", (error) => {
  console.error(`Unable to start Open Books with ${python}: ${error.message}`);
  process.exitCode = 1;
});
engine.on("exit", (code) => { process.exitCode = code ?? 1; });
