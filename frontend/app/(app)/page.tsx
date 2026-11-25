"use client";
import Link from "next/link";
import { useState } from "react";
import useSWR from "swr";
import { Dialog } from "@/components/Dialog";
import { api, fetcher } from "@/lib/api";
import type { Model } from "@/lib/types";

export default function Models() {
  const { data, error, isLoading, mutate } = useSWR<Model[]>("/models", fetcher);
  const [adding, setAdding] = useState(false);

  return (
    <>
      <div className="kopf">
        <div>
          <h1>Models</h1>
          <p className="leise">Jedes Model hat eigene Nischen. Aus freigegebenen Nischen entsteht später der Content.</p>
        </div>
        <button className="knopf haupt" onClick={() => setAdding(true)}>Model anlegen</button>
      </div>

      {error && <div className="hinweis fehler" role="alert">{error.message}<button className="knopf schmal" onClick={() => mutate()}>Neu laden</button></div>}
      {isLoading && <p className="leise">Lade Models …</p>}

      {data && data.length === 0 && (
        <div className="karte leer">
          <h2>Noch kein Model</h2>
          <p className="leise">Leg dein erstes Model an. Ein Name und ein Satz zum Typ reichen, damit die KI passende Nischen vorschlagen kann.</p>
          <button className="knopf haupt" onClick={() => setAdding(true)}>Model anlegen</button>
        </div>
      )}

      <div className="models">
        {data?.map((m) => {
          const c = m.nicheCounts ?? { Proposed: 0, Approved: 0, Rejected: 0 };
          return (
            <Link key={m.id} href={`/models/${m.id}`} className="karte model">
              <span className="kopfbild" aria-hidden="true">{m.name.trim().charAt(0).toUpperCase()}</span>
              <div>
                <h3>{m.name}</h3>
                <p className="leise">{m.vibe || "Noch keine Beschreibung"}</p>
              </div>
              <div className="zaehler">
                {c.Proposed > 0 && <div className="wartet"><b>{c.Proposed}</b><span className="klein leise">warten auf dich</span></div>}
                <div><b>{c.Approved}</b><span className="klein leise">{c.Approved === 1 ? "Nische frei" : "Nischen frei"}</span></div>
              </div>
            </Link>
          );
        })}
      </div>

      {adding && <NewModel onClose={() => setAdding(false)} onSaved={() => { setAdding(false); mutate(); }} />}
    </>
  );
}

function NewModel({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [vibe, setVibe] = useState("");
  const [market, setMarket] = useState<"DE" | "US">("DE");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.createModel({ name: name.trim(), vibe: vibe.trim(), market, language: market === "US" ? "English" : "German" });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Dialog title="Model anlegen" onClose={onClose}
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" form="neues-model" disabled={busy || !name.trim()}>{busy ? "Speichere …" : "Model anlegen"}</button>
      </>}>
      <form id="neues-model" className="formular" onSubmit={save}>
        <label className="feld">
          <span>Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} required autoFocus />
        </label>
        <label className="feld">
          <span>Typ und Ausstrahlung</span>
          <textarea value={vibe} onChange={(e) => setVibe(e.target.value)} maxLength={2000}
            placeholder="z. B. sportliche Blondine aus München, frech und nahbar" />
          <small>Je genauer, desto passender werden die Nischen-Vorschläge.</small>
        </label>
        <label className="feld">
          <span>Markt</span>
          <select value={market} onChange={(e) => setMarket(e.target.value as "DE" | "US")}>
            <option value="DE">Deutschland (Texte auf Deutsch)</option>
            <option value="US">USA (Texte auf Englisch)</option>
          </select>
        </label>
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
      </form>
    </Dialog>
  );
}
