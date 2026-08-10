"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(body.detail ?? "sign-in failed");
        return;
      }
      router.push("/");
      router.refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell">
      <form className="panel login" onSubmit={submit}>
        <h1>TradingAgents Control</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Sign in to view and control the bot.
        </p>
        <div style={{ marginTop: 16 }}>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Dashboard password"
            autoFocus
            autoComplete="current-password"
          />
        </div>
        <button
          className="primary"
          type="submit"
          disabled={busy || !password}
          style={{ marginTop: 12, width: "100%" }}
        >
          {busy ? "Signing in…" : "Sign in"}
        </button>
        {error ? <div className="error">{error}</div> : null}
      </form>
    </main>
  );
}
