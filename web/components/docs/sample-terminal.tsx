"use client";

import { useId, useState, type FormEvent } from "react";
import { runFiles } from "@/lib/engine-client";
import type { EngineDoc } from "@/lib/types";

const sampleUrl = "/examples/statement.csv";
const refusalCommand = "openbooks run statement.csv --currency INR --date-order dmy";
const releaseCommand = refusalCommand + " --opening 1000.00";

export function SampleTerminal() {
  const id = useId();
  const [command, setCommand] = useState(refusalCommand);
  const [lastCommand, setLastCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("Run the sample as-is, then supply the opening balance.");
  const [output, setOutput] = useState<EngineDoc | null>(null);

  async function execute(input: string) {
    if (busy) return;
    const value = input.trim().replace(/\s+/g, " ");
    setCommand(value);
    setLastCommand(value);
    setOutput(null);

    if (value === "help" || (value !== refusalCommand && value !== releaseCommand)) {
      setStatus("Choose either sample command below. Both use the same synthetic file.");
      return;
    }

    setBusy(true);
    setStatus("Running the sample through Open Books…");
    try {
      const signal = AbortSignal.timeout(30_000);
      const sample = await fetch(sampleUrl, { signal });
      if (!sample.ok) throw new Error("The synthetic CSV could not be loaded.");

      const file = new File([await sample.blob()], "statement.csv", { type: "text/csv" });
      const opening = value === releaseCommand ? "1000.00" : undefined;
      let result: EngineDoc | undefined;
      for await (const event of runFiles([file], { currency: "INR", date_order: "dmy", opening }, {}, signal)) {
        if (event.type === "done") result = event.doc;
      }

      if (!result) throw new Error("The engine returned no document.");
      setStatus(result.status === "ok" ? "Released. Inspect the transactions, assertions and evidence below." : result.error.code + " · " + result.error.message);
      setOutput(result);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "The engine could not complete this run.");
    } finally {
      setBusy(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void execute(command);
  }

  return (
    <section className="ob-terminal not-prose" aria-labelledby={id + "-title"}>
      <h3 id={id + "-title"}>Sample terminal</h3>
      <p id={id + "-hint"}>Commands run the bundled CSV through the live engine. Type <code>help</code> for the supported commands.</p>
      <form onSubmit={submit}>
        <label className="sr-only" htmlFor={id + "-command"}>Sample command</label>
        <span aria-hidden="true">$</span>
        <input id={id + "-command"} aria-describedby={id + "-hint"} value={command} onChange={(event) => setCommand(event.target.value)} autoComplete="off" spellCheck={false} maxLength={160} />
        <button type="submit" disabled={busy || command.trim() === ""}>{busy ? "Running…" : "Run"}</button>
      </form>
      <div className="ob-terminal-actions">
        <button type="button" disabled={busy} onClick={() => void execute(refusalCommand)}>Run without opening</button>
        <button type="button" disabled={busy} onClick={() => void execute(releaseCommand)}>Run with opening</button>
      </div>
      {lastCommand && <code className="ob-terminal-command">$ {lastCommand}</code>}
      <p role="status">{status}</p>
      {output && (
        <pre tabIndex={0} aria-label="Open Books engine JSON output"><code>{JSON.stringify(output, null, 2)}</code></pre>
      )}
    </section>
  );
}
