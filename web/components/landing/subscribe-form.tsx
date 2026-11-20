"use client";

import { useId, useState, type FormEvent } from "react";
import s from "@/app/landing.module.css";

type State = { kind: "idle" } | { kind: "sending" } | { kind: "done" } | { kind: "error"; message: string };

export function SubscribeForm() {
  const id = useId();
  const [state, setState] = useState<State>({ kind: "idle" });

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setState({ kind: "sending" });
    try {
      const res = await fetch("/api/subscribe", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: String(form.get("email") ?? ""), website: String(form.get("website") ?? "") }),
      });
      if (res.ok) return setState({ kind: "done" });
      const data = (await res.json().catch(() => null)) as { message?: string } | null;
      const fallback = res.status === 429 ? "Too many attempts. Please wait a minute and try again." : "Something went wrong. Please try again.";
      setState({ kind: "error", message: data?.message ?? fallback });
    } catch {
      setState({ kind: "error", message: "You appear to be offline. Check your connection and try again." });
    }
  }

  if (state.kind === "done") {
    return (
      <p className={`${s.subscribeDone} ${s.display}`} role="status">
        You&rsquo;re on the list. We&rsquo;ll email you when something ships.
      </p>
    );
  }

  return (
    <form className={s.subscribe} onSubmit={onSubmit} noValidate={false}>
      <label htmlFor={`${id}-email`} className={s.subscribeLabel}>Email address</label>
      <div className={s.subscribeRow}>
        <input id={`${id}-email`} name="email" type="email" inputMode="email" autoComplete="email" placeholder="you@company.com" required maxLength={254} aria-describedby={`${id}-hint`} className={s.input} />
        <input name="website" tabIndex={-1} autoComplete="off" aria-hidden="true" className={s.honeypot} />
        <button type="submit" className={`${s.btn} ${s.btnDark}`} disabled={state.kind === "sending"}>
          {state.kind === "sending" ? "Subscribing…" : "Subscribe"}
        </button>
      </div>
      <p id={`${id}-hint`} className={s.subscribeHint}>Product updates only: one email when something ships, never your documents.</p>
      {state.kind === "error" && <p role="alert" className={s.subscribeError}>{state.message}</p>}
    </form>
  );
}
