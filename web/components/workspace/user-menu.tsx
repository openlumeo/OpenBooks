"use client";

import { LogOut } from "lucide-react";
import { useState } from "react";
import { authClient } from "@/lib/auth/client";

export function UserMenu() {
  const { data: session } = authClient.useSession();
  const [busy, setBusy] = useState(false);
  const user = session?.user;
  if (!user) return null;

  async function signOut() {
    setBusy(true);
    try {
      await authClient.signOut();
    } finally {
      window.location.assign("/");
    }
  }

  return (
    <div className="ob-user" role="group" aria-label="Account">
      <span className="ob-user-name" title={user.email}>
        {user.name || user.email}
      </span>
      <button type="button" className="copy-inline ob-user-out" onClick={signOut} disabled={busy}>
        <LogOut size={13} aria-hidden="true" />
        <span>{busy ? "Signing out…" : "Sign out"}</span>
      </button>
    </div>
  );
}
