"use client";

import Link from "next/link";
import { Instrument_Serif } from "next/font/google";
import { useId, useState, type FormEvent } from "react";
import { authClient } from "@/lib/auth/client";
import s from "./auth-form.module.css";

const serif = Instrument_Serif({ weight: "400", subsets: ["latin"], variable: "--font-display", display: "swap" });

type Mode = "sign-up" | "sign-in";

const COPY = {
  "sign-up": { title: "Create your account", sub: "One account for the workspace. It takes under a minute.", cta: "Create account", busy: "Creating account…", alt: ["Already have an account?", "Sign in", "/auth/sign-in"] },
  "sign-in": { title: "Welcome back", sub: "Sign in to pick up where you left off.", cta: "Sign in", busy: "Signing in…", alt: ["New to Open Books?", "Create an account", "/auth/sign-up"] },
} as const;

/** Turn the auth server's terse errors into a sentence that names the problem and the fix. */
function friendly(message: string | undefined, mode: Mode): string {
  const m = (message ?? "").toLowerCase();
  if (m.includes("exist")) return "An account with that email already exists. Try signing in instead.";
  if (m.includes("invalid") && mode === "sign-in") return "That email and password don't match. Check them and try again.";
  if (m.includes("password") && m.includes("short")) return "Use a password of at least 8 characters.";
  return message ?? "Something went wrong. Please try again.";
}

export function AuthForm({ mode }: { mode: Mode }) {
  const id = useId();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [show, setShow] = useState(false);
  const copy = COPY[mode];

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email"));
    const password = String(form.get("password"));
    setBusy(true);
    setError(null);
    try {
      const { error } =
        mode === "sign-up"
          ? await authClient.signUp.email({ name: String(form.get("name")), email, password })
          : await authClient.signIn.email({ email, password });
      if (error) {
        setError(friendly(error.message, mode));
        setBusy(false);
      } else {
        window.location.assign("/app");
      }
    } catch {
      setError("We couldn't reach the server. Check your connection and try again.");
      setBusy(false);
    }
  }

  async function withGoogle() {
    setError(null);
    setBusy(true);
    const { error } = await authClient.signIn.social({ provider: "google", callbackURL: "/app" });
    if (error) {
      setError("Google sign-in isn't available right now. Use your email instead.");
      setBusy(false);
    }
  }

  return (
    <div className={`${serif.variable} ${s.page}`}>
      <main className={s.shell}>
        <Link href="/" className={s.back}>&larr; Open Books</Link>
        <h1 className={s.title}>{copy.title}</h1>
        <p className={s.sub}>{copy.sub}</p>

        <button type="button" className={`${s.btn} ${s.google}`} onClick={withGoogle} disabled={busy}>Continue with Google</button>
        <div className={s.divider} role="separator" aria-label="or">or</div>

        <form className={s.form} onSubmit={onSubmit}>
          {mode === "sign-up" && (
            <div className={s.field}>
              <label className={s.label} htmlFor={`${id}-name`}>Name</label>
              <input id={`${id}-name`} className={s.input} name="name" autoComplete="name" required />
            </div>
          )}
          <div className={s.field}>
            <label className={s.label} htmlFor={`${id}-email`}>Email</label>
            <input id={`${id}-email`} className={s.input} name="email" type="email" inputMode="email" autoComplete="email" required aria-invalid={error ? true : undefined} />
          </div>
          <div className={s.field}>
            <label className={s.label} htmlFor={`${id}-pw`}>Password</label>
            <div className={s.inputWrap}>
              <input id={`${id}-pw`} className={`${s.input} ${s.hasToggle}`} name="password" type={show ? "text" : "password"} autoComplete={mode === "sign-up" ? "new-password" : "current-password"} minLength={8} required aria-describedby={mode === "sign-up" ? `${id}-pwhint` : undefined} aria-invalid={error ? true : undefined} />
              <button type="button" className={s.toggle} onClick={() => setShow((v) => !v)} aria-pressed={show}>{show ? "Hide" : "Show"}</button>
            </div>
            {mode === "sign-up" && <p id={`${id}-pwhint`} className={s.hint}>At least 8 characters.</p>}
          </div>
          {error && <p role="alert" className={s.error}>{error}</p>}
          <button type="submit" className={`${s.btn} ${s.primary}`} disabled={busy}>{busy ? copy.busy : copy.cta}</button>
        </form>

        <p className={s.alt}>{copy.alt[0]} <Link href={copy.alt[2]}>{copy.alt[1]}</Link></p>
        {mode === "sign-up" && <p className={s.legal}>Open Books is in a training phase. We never keep your documents for training unless you opt in, upload by upload.</p>}
      </main>
    </div>
  );
}
