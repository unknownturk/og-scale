"use client";
import { useState } from "react";

export default function Login() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    const res = await fetch("/api/login", { method: "POST", body: JSON.stringify({ password }) }).catch(() => null);
    if (res?.ok) {
      window.location.href = "/";
      return;
    }
    const body = await res?.json().catch(() => null);
    setError(body?.detail || "Keine Verbindung. Versuch es noch einmal.");
    setBusy(false);
  }

  return (
    <main className="anmeldung">
      <form onSubmit={submit}>
        <div className="marke">OG <span>Scale</span></div>
        <label className="feld">
          <span>Passwort</span>
          <input type="password" autoFocus autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
        </label>
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
        <button className="knopf haupt" disabled={busy}>{busy ? "Prüfe …" : "Anmelden"}</button>
      </form>
    </main>
  );
}
