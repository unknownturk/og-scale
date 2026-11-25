"use client";
import { useRef, useState } from "react";
import { api, mediaUrl } from "@/lib/api";
import type { Model } from "@/lib/types";

const MAX = 6;
const BODY_TYPES: [Model["bodyType"], string][] = [
  ["normal", "Normal"], ["slim", "Schlank"], ["curvy", "Kurvig"], ["athletic", "Sportlich"], ["busty", "Große Oberweite"],
];

/** Referenzfotos und Figur eines Models — daran erkennt die Bild-KI ihr Gesicht. */
export function References({ model, onChanged }: { model: Model; onChanged: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const photos = model.referenceImages ?? [];

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <section className="karte referenzen">
      <div className="referenzen-kopf">
        <div>
          <h2>Referenzfotos</h2>
          <p className="leise klein">
            {photos.length === 0
              ? "Ohne Referenzfotos kann kein Content entstehen. Lade zwei bis sechs klare Fotos ihres Gesichts hoch."
              : "An diesen Fotos erkennt die Bild-KI ihr Gesicht. Mehr Fotos ergeben eine höhere Ähnlichkeit."}
          </p>
        </div>
        <label className="feld figur">
          <span>Figur</span>
          <select value={model.bodyType || "normal"} disabled={busy}
            onChange={(e) => run(() => api.updateModel(model.id, { bodyType: e.target.value as Model["bodyType"] }))}>
            {BODY_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>
      <div className="fotos">
        {photos.map((_, i) => (
          <figure key={`${i}-${photos.length}`}>
            <img src={mediaUrl("models", model.id, "referenceImages", i)} alt={`Referenzfoto ${i + 1}`} loading="lazy" />
            <button className="entfernen" disabled={busy} aria-label={`Referenzfoto ${i + 1} entfernen`}
              onClick={() => run(() => api.removeReference(model.id, i))}>×</button>
          </figure>
        ))}
        {photos.length < MAX && (
          <button className="foto-neu" disabled={busy} onClick={() => input.current?.click()}>
            {busy ? "Lade hoch …" : "Fotos hochladen"}
          </button>
        )}
      </div>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" multiple hidden
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (!files.length) return;
          if (photos.length + files.length > MAX) {
            setError(`Höchstens ${MAX} Fotos. Du kannst noch ${MAX - photos.length} hochladen.`);
            return;
          }
          run(() => api.addReferences(model.id, files));
        }} />
      {error && <div className="hinweis fehler" role="alert">{error}</div>}
    </section>
  );
}
