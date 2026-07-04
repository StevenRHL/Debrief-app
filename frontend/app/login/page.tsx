"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { login } from "../../lib/api";
import { saveSession } from "../../lib/auth";

export default function Login() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const session = await login(username.trim(), password);
      saveSession(session);
      router.push("/progress");
    } catch (e: any) {
      setErr(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="narrow">
      <div className="card">
        <h2>Sign in</h2>
        <div className="mock-banner">
          <strong>Mock auth.</strong> Any username and password signs you in with a local fake
          session — no Cognito, no network. The same form talks to the real user pool once the app
          goes live.
        </div>
        <form onSubmit={onSubmit} className="auth-form">
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          <button type="submit" disabled={busy || !username.trim() || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          {err && <div className="guard-msg error">{err}</div>}
        </form>
      </div>
    </main>
  );
}
