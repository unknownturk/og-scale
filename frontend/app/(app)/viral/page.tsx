"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";
import { Dialog } from "@/components/Dialog";
import { api, fetcher } from "@/lib/api";
import type { Model, Niche, ScrapeResult, Source, ViralReel, ViralStatus } from "@/lib/types";
import { useJob } from "@/lib/useJob";

const compact = (n: number) => new Intl.NumberFormat("de-DE", { notation: "compact", maximumFractionDigits: 1 }).format(n);

function ago(iso: string) {
  const hours = (Date.now() - new Date(iso).getTime()) / 3_600_000;
  if (!iso || Number.isNaN(hours)) return "";
  if (hours < 1) return "gerade eben";
  if (hours < 24) return `vor ${Math.round(hours)} Std.`;
  return `vor ${Math.round(hours / 24)} Tagen`;
}

export default function ViralPage() {
  const [sort, setSort] = useState("potential");
  const [market, setMarket] = useState("");
  const reels = useSWR<ViralReel[]>(`/viral/reels?sort=${sort}&market=${market}`, fetcher);
  const status = useSWR<ViralStatus>("/viral/status", fetcher);
  const sources = useSWR<Source[]>("/viral/sources", fetcher);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [dialog, setDialog] = useState<"" | "sources" | "import">("");
  const [watching, setWatching] = useState<string | null>(null);
  const job = useJob<ScrapeResult>(() => { reels.mutate(); status.mutate(); sources.mutate(); });

  // Nur noch sichtbare Reels bleiben ausgewählt.
  useEffect(() => {
    const visible = new Set((reels.data ?? []).map((r) => r.id));
    setChosen((old) => new Set([...old].filter((id) => visible.has(id))));
  }, [reels.data]);

  const toggle = (id: string) => setChosen((old) => {
    const next = new Set(old);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });
  const active = (sources.data ?? []).filter((s) => s.state === "Active").length;
  const result = job.result;

  return (
    <>
      <div className="kopf">
        <div>
          <h1>Viral</h1>
          <p className="leise">
            Die stärksten Reels deiner Quellen, sortiert nach Potenzial. Wähle Vorlagen aus und verwandle sie in Motion-Reels.
            {status.data?.lastScrape && ` Zuletzt gelesen ${ago(status.data.lastScrape)}.`}
          </p>
        </div>
        <div className="reihe">
          <button className="knopf" onClick={() => setDialog("sources")}>Quellen ({sources.data?.length ?? 0})</button>
          <button className="knopf haupt" disabled={job.running || status.data?.running || active === 0}
            onClick={() => job.track(() => api.scrapeViral())}>
            {job.running || status.data?.running ? "Lese …" : "Jetzt neu lesen"}</button>
        </div>
      </div>

      {status.data && !status.data.provider && <div className="hinweis info">Zum Lesen fremder Reels fehlt noch ein Zugang (HikerAPI oder Apify).</div>}
      {job.running && <div className="hinweis arbeit" role="status"><span className="reihe"><span className="puls" />Lese {active} {active === 1 ? "Quelle" : "Quellen"}. Das kann einige Minuten dauern.</span></div>}
      {job.error && <div className="hinweis fehler" role="alert">{job.error}<button className="knopf schmal" onClick={job.reset}>Schließen</button></div>}
      {result && (
        <div className={`hinweis ${result.errors.length ? "info" : "arbeit"}`} role="status">
          <span>
            {result.created} neue Reels aus {result.sourcesWithReels} von {result.sources} Quellen.
            {result.errors.length > 0 && ` ${result.errors.length} Problem(e): ${result.errors.slice(0, 2).join("; ")}`}
          </span>
          <button className="knopf schmal" onClick={job.reset}>Schließen</button>
        </div>
      )}

      <div className="reihe leiste-filter">
        <label className="feld filter"><span className="nur-leser">Sortierung</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="potential">Nach Potenzial</option>
            <option value="views">Nach Views</option>
            <option value="outperform">Nach Ausreißer (mal üblich)</option>
            <option value="recent">Neueste zuerst</option>
          </select></label>
        <label className="feld filter"><span className="nur-leser">Markt</span>
          <select value={market} onChange={(e) => setMarket(e.target.value)}>
            <option value="">Alle Märkte</option><option value="DE">Deutschland</option><option value="US">USA</option>
          </select></label>
      </div>

      {reels.error && <div className="hinweis fehler" role="alert">{reels.error.message}</div>}
      {reels.isLoading && <p className="leise">Lade Reels …</p>}
      {reels.data?.length === 0 && (
        <div className="karte leer">
          <h2>{sources.data?.length ? "Noch keine Reels" : "Noch keine Quellen"}</h2>
          <p className="leise">{sources.data?.length
            ? "Lies deine Quellen, um ihre aktuellen Reels zu holen."
            : "Trag Instagram-Accounts ein, deren Reels du als Vorlage nutzen willst."}</p>
          {sources.data?.length
            ? <button className="knopf haupt" disabled={job.running || active === 0} onClick={() => job.track(() => api.scrapeViral())}>Jetzt neu lesen</button>
            : <button className="knopf haupt" onClick={() => setDialog("sources")}>Quellen eintragen</button>}
        </div>
      )}

      <div className="viral">
        {reels.data?.map((r) => (
          <article key={r.id} className={`karte v-karte${chosen.has(r.id) ? " gewaehlt" : ""}`}>
            <button className="v-bild" onClick={() => setWatching(r.id)} aria-label={`Reel von ${r.owner} ansehen`}>
              <img src={`/api/proxy/viral/reels/${r.id}/thumbnail`} alt="" loading="lazy"
                onError={(e) => { e.currentTarget.style.visibility = "hidden"; }} />
              <span className="potenzial" title="Potenzial von 0 bis 100"><b>{r.potential}</b></span>
              {r.status === "Imported" && <span className="benutzt">verwendet</span>}
            </button>
            <div className="v-text">
              <p className="v-kopf"><b>@{r.owner}</b><span className="leise klein">{ago(r.postedAt)}</span></p>
              <p className="zahlen">
                <span><b>{compact(r.views)}</b> Views</span>
                <span><b>{compact(r.likes)}</b> Likes</span>
                <span title="Views im Verhältnis zum üblichen Reel dieses Accounts"><b>{r.outperform.toLocaleString("de-DE")}×</b> üblich</span>
              </p>
              {r.caption && <p className="klein leise v-caption">{r.caption}</p>}
            </div>
            <div className="aktionen">
              <label className="reihe wahl"><input type="checkbox" checked={chosen.has(r.id)} onChange={() => toggle(r.id)} /><span>Auswählen</span></label>
              <div className="rechts">
                {r.status !== "Imported" && <button className="knopf still schmal"
                  onClick={async () => { await api.setViralStatus(r.id, "Dismissed"); reels.mutate(); }}>Ausblenden</button>}
              </div>
            </div>
          </article>
        ))}
      </div>

      {chosen.size > 0 && (
        <div className="auswahl" role="region" aria-label="Auswahl">
          <span><b>{chosen.size}</b> {chosen.size === 1 ? "Vorlage" : "Vorlagen"} ausgewählt</span>
          <button className="knopf still schmal" onClick={() => setChosen(new Set())}>Auswahl leeren</button>
          <button className="knopf haupt" onClick={() => setDialog("import")}>In Reels verwandeln</button>
        </div>
      )}

      {dialog === "sources" && <SourcesDialog sources={sources.data ?? []} onChanged={() => sources.mutate()} onClose={() => setDialog("")} />}
      {dialog === "import" && <ImportDialog ids={[...chosen]} onClose={() => setDialog("")}
        onDone={() => { setDialog(""); setChosen(new Set()); reels.mutate(); }} />}
      {watching && (
        <Dialog title={`@${reels.data?.find((r) => r.id === watching)?.owner ?? ""}`} onClose={() => setWatching(null)}
          footer={<>
            <a className="knopf" href={reels.data?.find((r) => r.id === watching)?.reelUrl} target="_blank" rel="noreferrer">Auf Instagram öffnen</a>
            <button className="knopf still" onClick={() => setWatching(null)}>Schließen</button>
          </>}>
          <video className="gross" controls autoPlay playsInline src={`/api/proxy/viral/reels/${watching}/video`} />
        </Dialog>
      )}
    </>
  );
}

function SourcesDialog({ sources, onChanged, onClose }: { sources: Source[]; onChanged: () => void; onClose: () => void }) {
  const [text, setText] = useState("");
  const [market, setMarket] = useState<"DE" | "US">("DE");
  const [category, setCategory] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const handles = text.split(/[\n,\s]+/).map((h) => h.trim()).filter(Boolean);

  async function run(action: () => Promise<void>) {
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

  return (
    <Dialog wide title="Quellen" intro="Instagram-Accounts, deren Reels gelesen und bewertet werden." onClose={onClose}
      footer={<button className="knopf still" onClick={onClose}>Fertig</button>}>
      <div className="formular">
        <label className="feld"><span>Accounts hinzufügen</span>
          <textarea rows={3} value={text} onChange={(e) => setText(e.target.value)} placeholder={"Namen oder Profil-Links, einer pro Zeile"} /></label>
        <div className="zwei">
          <label className="feld"><span>Markt</span>
            <select value={market} onChange={(e) => setMarket(e.target.value as "DE" | "US")}>
              <option value="DE">Deutschland</option><option value="US">USA</option></select></label>
          <label className="feld"><span>Kategorie</span>
            <input value={category} onChange={(e) => setCategory(e.target.value)} maxLength={60} placeholder="z. B. Gym" /></label>
        </div>
        <div className="reihe">
          <button className="knopf haupt" disabled={busy || handles.length === 0}
            onClick={() => run(async () => {
              const res = await api.addSources(handles, market, category);
              setText("");
              setNote(`${res.created.length} hinzugefügt${res.skipped.length ? `, ${res.skipped.length} übersprungen (schon vorhanden oder ungültig)` : ""}.`);
            })}>
            {handles.length <= 1 ? "Account hinzufügen" : `${handles.length} Accounts hinzufügen`}</button>
          {note && <span className="leise klein">{note}</span>}
        </div>
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
        {sources.length > 0 && (
          <ul className="quellen">
            {sources.map((s) => (
              <li key={s.id} className={s.state === "Disabled" ? "aus" : undefined}>
                <span><b>@{s.handle}</b> <span className="leise klein">{s.market}{s.category ? `, ${s.category}` : ""}{s.lastScraped ? `, gelesen ${ago(s.lastScraped)}` : ", noch nie gelesen"}</span></span>
                <span className="reihe">
                  <button className="knopf still schmal" disabled={busy}
                    onClick={() => run(async () => { await api.updateSource(s.id, { state: s.state === "Active" ? "Disabled" : "Active" }); })}>
                    {s.state === "Active" ? "Pausieren" : "Wieder lesen"}</button>
                  <button className="knopf still schmal" disabled={busy} onClick={() => run(() => api.deleteSource(s.id))}>Entfernen</button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}

function ImportDialog({ ids, onClose, onDone }: { ids: string[]; onClose: () => void; onDone: () => void }) {
  const models = useSWR<Model[]>("/models", fetcher);
  const [modelId, setModelId] = useState("");
  const current = modelId || models.data?.[0]?.id || "";
  const niches = useSWR<Niche[]>(current ? `/models/${current}/niches` : null, fetcher);
  const approved = useMemo(() => (niches.data ?? []).filter((n) => n.status === "Approved"), [niches.data]);
  const [nicheId, setNicheId] = useState("");
  const [variants, setVariants] = useState(1);
  const [videoModel, setVideoModel] = useState<"kling-3.0" | "kling-2.6">("kling-3.0");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const model = models.data?.find((m) => m.id === current);
  const niche = approved.find((n) => n.id === nicheId) ?? approved[0];
  const total = ids.length * variants;
  const noPhotos = model && !(model.referenceImages ?? []).length;

  async function start() {
    if (!niche) return;
    setBusy(true);
    setError("");
    try {
      await api.importViral(ids, niche.id, variants, videoModel);
      onDone();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <Dialog title="In Reels verwandeln" onClose={onClose}
      intro="Für jede Vorlage entsteht zuerst ein Bild mit deinem Model. Das Video startet erst, wenn du das Bild freigibst."
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" disabled={busy || !niche || !!noPhotos || total > 30} onClick={start}>
          {busy ? "Starte …" : total === 1 ? "Ein Reel starten" : `${total} Reels starten`}</button>
      </>}>
      <div className="formular">
        <div className="zwei">
          <label className="feld"><span>Model</span>
            <select value={current} onChange={(e) => { setModelId(e.target.value); setNicheId(""); }}>
              {models.data?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
          <label className="feld"><span>Nische</span>
            <select value={niche?.id ?? ""} onChange={(e) => setNicheId(e.target.value)} disabled={!approved.length}>
              {approved.length === 0 && <option value="">Keine freigegebene Nische</option>}
              {approved.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
        </div>
        {noPhotos && <div className="hinweis info">{model?.name} hat noch keine Referenzfotos.<Link className="knopf schmal" href={`/models/${current}`}>Fotos hochladen</Link></div>}
        <div className="zwei">
          <label className="feld"><span>Fassungen pro Vorlage</span>
            <select value={variants} onChange={(e) => setVariants(Number(e.target.value))}>
              <option value={1}>Eine</option><option value={2}>Zwei</option><option value={3}>Drei</option></select>
            <small>Mehrere Fassungen, wenn mehrere Accounts dieselbe Vorlage posten sollen. Jede kostet ein Bild und ein Video.</small></label>
          <label className="feld"><span>Video-Modell</span>
            <select value={videoModel} onChange={(e) => setVideoModel(e.target.value as typeof videoModel)}>
              <option value="kling-3.0">Kling 3.0</option><option value="kling-2.6">Kling 2.6</option></select></label>
        </div>
        {total > 30 && <div className="hinweis info">Das wären {total} Reels. Höchstens 30 pro Durchgang.</div>}
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
      </div>
    </Dialog>
  );
}
