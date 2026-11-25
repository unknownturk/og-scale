"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { Dialog } from "@/components/Dialog";
import { api, fetcher, mediaUrl } from "@/lib/api";
import type { Content, ContentStatus, Model, Niche, PhotoMode } from "@/lib/types";

const SECTIONS: { status: ContentStatus; title: string }[] = [
  { status: "Review", title: "Warten auf deine Freigabe" },
  { status: "Failed", title: "Brauchen dich" },
  { status: "Working", title: "In Arbeit" },
  { status: "Approved", title: "Freigegeben" },
];

const MODES: [PhotoMode, string][] = [
  ["niche", "Nische (Outfits und Orte der Nische)"],
  ["lifestyle", "Lifestyle (Café, Straße, Alltagsmode)"],
  ["story_daily", "Alltag (Morgen, Spiegel, Zuhause)"],
  ["story_me", "Porträt (Nahaufnahme)"],
  ["story_cta", "Zuhause, einladend"],
];

export default function ContentPage() {
  const models = useSWR<Model[]>("/models", fetcher);
  const [modelId, setModelId] = useState("");
  const content = useSWR<Content[]>(`/content${modelId ? `?modelId=${modelId}` : ""}`, fetcher, {
    // Solange etwas in Arbeit ist, alle drei Sekunden nachsehen.
    refreshInterval: (data) => (data?.some((c) => c.status === "Working") ? 3000 : 0),
  });
  const [creating, setCreating] = useState(false);
  const names = useMemo(() => new Map((models.data ?? []).map((m) => [m.id, m.name])), [models.data]);
  const by = (status: ContentStatus) => (content.data ?? []).filter((c) => c.status === status);
  const rejected = by("Rejected");
  const refresh = () => content.mutate();

  return (
    <>
      <div className="kopf">
        <div>
          <h1>Content</h1>
          <p className="leise">Carousels und Fotos aus deinen freigegebenen Nischen. Nichts gilt als fertig, bevor du es freigibst.</p>
        </div>
        <div className="reihe">
          <label className="feld filter">
            <span className="nur-leser">Model</span>
            <select value={modelId} onChange={(e) => setModelId(e.target.value)}>
              <option value="">Alle Models</option>
              {models.data?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>
          </label>
          <button className="knopf haupt" onClick={() => setCreating(true)}>Content erzeugen</button>
        </div>
      </div>

      {content.error && <div className="hinweis fehler" role="alert">{content.error.message}<button className="knopf schmal" onClick={refresh}>Neu laden</button></div>}
      {content.isLoading && <p className="leise">Lade Content …</p>}

      {content.data?.length === 0 && (
        <div className="karte leer">
          <h2>Noch kein Content</h2>
          <p className="leise">Wähle ein Model und eine freigegebene Nische. Daraus entstehen Carousels oder einzelne Fotos.</p>
          <button className="knopf haupt" onClick={() => setCreating(true)}>Content erzeugen</button>
        </div>
      )}

      {SECTIONS.map(({ status, title }) => {
        const items = by(status);
        if (!items.length) return null;
        return (
          <section key={status} className="abschnitt">
            <header><span className={`punkt c-${status}`} /><h2>{title}</h2><span className="leise">{items.length}</span></header>
            <div className="kacheln">
              {items.map((c) => <Tile key={c.id} content={c} model={names.get(c.modelId) ?? ""} onChanged={refresh} />)}
            </div>
          </section>
        );
      })}

      {rejected.length > 0 && (
        <details className="abschnitt eingeklappt">
          <summary><span className="punkt c-Rejected" /><h2>Abgelehnt</h2><span className="leise">{rejected.length}, zum Aufklappen tippen</span></summary>
          <div className="kacheln">
            {rejected.map((c) => <Tile key={c.id} content={c} model={names.get(c.modelId) ?? ""} onChanged={refresh} />)}
          </div>
        </details>
      )}

      {creating && <CreateDialog models={models.data ?? []} preset={modelId} onClose={() => setCreating(false)}
        onCreated={() => { setCreating(false); refresh(); }} />}
    </>
  );
}

function Tile({ content, model, onChanged }: { content: Content; model: string; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [open, setOpen] = useState<number | null>(null);

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
    }
  }
  const working = content.status === "Working";
  const missing = content.slotCount - content.imageCount;

  return (
    <article className={`karte kachel c-${content.status}`}>
      <div className={`bilder n${Math.min(content.slotCount, 4)}`}>
        {Array.from({ length: content.slotCount }).map((_, i) =>
          i < content.imageCount ? (
            <button key={i} className="bild" onClick={() => setOpen(i)} aria-label={`Bild ${i + 1} vergrößern`}>
              <img src={mediaUrl("content", content.id, "images", i)} alt="" loading="lazy" />
            </button>
          ) : (
            <div key={i} className={`bild leerbild${working ? " laedt" : ""}`} aria-hidden="true" />
          ),
        )}
      </div>
      <div className="kachel-text">
        <h3>{content.title}</h3>
        <p className="leise klein">
          {model}
          {working && `, ${content.imageCount} von ${content.slotCount} Bildern fertig`}
          {!working && content.type === "Carousel" && `, ${content.imageCount} Bilder`}
        </p>
        {content.error && <p className={`klein ${content.status === "Failed" ? "warnung" : "leise"}`}>{content.error}</p>}
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
      </div>
      <div className="aktionen">
        {content.status === "Review" && <>
          <button className="knopf haupt schmal" disabled={busy} onClick={() => run(() => api.decideContent(content.id, "approve"))}>Freigeben</button>
          <button className="knopf schmal" disabled={busy} onClick={() => run(() => api.decideContent(content.id, "reject"))}>Ablehnen</button>
        </>}
        {(content.status === "Failed" || (content.status === "Review" && missing > 0)) &&
          <button className="knopf schmal" disabled={busy} onClick={() => run(() => api.retryContent(content.id))}>Erneut versuchen</button>}
        {(content.status === "Approved" || content.status === "Rejected") &&
          <button className="knopf schmal" disabled={busy} onClick={() => run(() => api.decideContent(content.id, "reopen"))}>Wieder prüfen</button>}
        {!working && (
          <div className="rechts">
            {confirmDelete ? <>
              <button className="knopf schmal gefahr" disabled={busy} onClick={() => run(() => api.deleteContent(content.id))}>Ja, löschen</button>
              <button className="knopf still schmal" onClick={() => setConfirmDelete(false)}>Nein</button>
            </> : <button className="knopf still schmal" onClick={() => setConfirmDelete(true)}>Löschen</button>}
          </div>
        )}
      </div>
      {open !== null && (
        <Dialog wide title={content.title} onClose={() => setOpen(null)}
          footer={<>
            {content.imageCount > 1 && <>
              <button className="knopf" onClick={() => setOpen((open + content.imageCount - 1) % content.imageCount)}>Vorheriges</button>
              <button className="knopf" onClick={() => setOpen((open + 1) % content.imageCount)}>Nächstes</button>
            </>}
            <button className="knopf still" onClick={() => setOpen(null)}>Schließen</button>
          </>}>
          <img className="gross" src={mediaUrl("content", content.id, "images", open)} alt={`Bild ${open + 1} von ${content.imageCount}`} />
        </Dialog>
      )}
    </article>
  );
}

function CreateDialog({ models, preset, onClose, onCreated }: {
  models: Model[]; preset: string; onClose: () => void; onCreated: () => void;
}) {
  const [modelId, setModelId] = useState(preset || models[0]?.id || "");
  const niches = useSWR<Niche[]>(modelId ? `/models/${modelId}/niches` : null, fetcher);
  const approved = (niches.data ?? []).filter((n) => n.status === "Approved");
  const [nicheId, setNicheId] = useState("");
  const [kind, setKind] = useState<"carousel" | "photos">("carousel");
  const [count, setCount] = useState(5);
  const [mode, setMode] = useState<PhotoMode>("niche");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const model = models.find((m) => m.id === modelId);
  const chosen = approved.find((n) => n.id === nicheId) ?? approved[0];
  const noPhotos = model && !(model.referenceImages ?? []).length;

  async function start(e: React.FormEvent) {
    e.preventDefault();
    if (!chosen) return;
    setBusy(true);
    setError("");
    try {
      await api.createImages(chosen.id, { kind, count, mode });
      onCreated();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Dialog title="Content erzeugen" intro="Die Bilder entstehen im Hintergrund und erscheinen hier, sobald sie fertig sind."
      onClose={onClose}
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" form="content-form" disabled={busy || !chosen || !!noPhotos}>
          {busy ? "Starte …" : kind === "carousel" ? `Carousel mit ${count} Bildern erzeugen` : count === 1 ? "Ein Foto erzeugen" : `${count} Fotos erzeugen`}
        </button>
      </>}>
      <form id="content-form" className="formular" onSubmit={start}>
        <div className="zwei">
          <label className="feld"><span>Model</span>
            <select value={modelId} onChange={(e) => { setModelId(e.target.value); setNicheId(""); }}>
              {models.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select></label>
          <label className="feld"><span>Nische</span>
            <select value={chosen?.id ?? ""} onChange={(e) => setNicheId(e.target.value)} disabled={!approved.length}>
              {approved.length === 0 && <option value="">Keine freigegebene Nische</option>}
              {approved.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
            </select></label>
        </div>
        {noPhotos && <div className="hinweis info">{model?.name} hat noch keine Referenzfotos.<Link className="knopf schmal" href={`/models/${modelId}`}>Fotos hochladen</Link></div>}
        {niches.data && approved.length === 0 && <div className="hinweis info">Gib zuerst eine Nische frei.<Link className="knopf schmal" href={`/models/${modelId}`}>Zu den Nischen</Link></div>}
        <div className="zwei">
          <label className="feld"><span>Was soll entstehen?</span>
            <select value={kind} onChange={(e) => setKind(e.target.value as "carousel" | "photos")}>
              <option value="carousel">Ein Carousel (ein Look, mehrere Posen)</option>
              <option value="photos">Einzelne Fotos (jedes mit eigenem Look)</option>
            </select></label>
          <label className="feld"><span>{kind === "carousel" ? "Bilder im Carousel" : "Anzahl Fotos"}</span>
            <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>{n}</option>)}
            </select></label>
        </div>
        <label className="feld"><span>Art der Aufnahme</span>
          <select value={mode} onChange={(e) => setMode(e.target.value as PhotoMode)}>
            {MODES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select></label>
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
      </form>
    </Dialog>
  );
}
