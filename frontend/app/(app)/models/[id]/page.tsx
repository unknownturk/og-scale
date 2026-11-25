"use client";
import Link from "next/link";
import { use, useState } from "react";
import useSWR from "swr";
import { Dialog } from "@/components/Dialog";
import { ImproveDialog, NicheCard, NicheEditor } from "@/components/niches";
import { References } from "@/components/References";
import { api, fetcher } from "@/lib/api";
import type { Model, Niche, NicheStatus } from "@/lib/types";
import { useJob } from "@/lib/useJob";

const SECTIONS: { status: NicheStatus; title: string; empty: string }[] = [
  { status: "Proposed", title: "Warten auf deine Entscheidung", empty: "" },
  { status: "Approved", title: "Freigegeben", empty: "Noch keine Nische freigegeben. Erst aus freigegebenen Nischen kann Content entstehen." },
];

export default function ModelPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const model = useSWR<Model>(`/models/${id}`, fetcher);
  const niches = useSWR<Niche[]>(`/models/${id}/niches`, fetcher);
  const [dialog, setDialog] = useState<"" | "generate" | "brief">("");
  const [editing, setEditing] = useState<Niche | null>(null);
  const [improving, setImproving] = useState<Niche | null>(null);
  const [working, setWorking] = useState("");
  const job = useJob<{ count: number }>(() => niches.mutate());

  const refresh = () => niches.mutate();
  const by = (status: NicheStatus) => (niches.data ?? []).filter((n) => n.status === status);
  const rejected = by("Rejected");

  function start(label: string, run: () => ReturnType<typeof api.generateNiches>) {
    setDialog("");
    setWorking(label);
    job.track(run);
  }

  if (model.error) {
    return <div className="hinweis fehler" role="alert">{model.error.message}<Link className="knopf schmal" href="/">Zur Übersicht</Link></div>;
  }

  return (
    <>
      <Link href="/" className="zurueck leise klein">← Alle Models</Link>
      <div className="kopf">
        <div>
          <h1>{model.data?.name ?? " "}</h1>
          <p className="leise">{model.data?.vibe}</p>
        </div>
        <div className="reihe">
          <button className="knopf" disabled={job.running} onClick={() => setDialog("brief")}>Nische aus Stichpunkten</button>
          <button className="knopf haupt" disabled={job.running} onClick={() => setDialog("generate")}>Nischen vorschlagen lassen</button>
        </div>
      </div>

      {model.data && <References model={model.data} onChanged={() => model.mutate()} />}

      {job.running && <div className="hinweis arbeit" role="status"><span className="reihe"><span className="puls" />{working} Das dauert bis zu zwei Minuten, du kannst hier bleiben.</span></div>}
      {job.error && <div className="hinweis fehler" role="alert">{job.error}<button className="knopf schmal" onClick={job.reset}>Schließen</button></div>}
      {job.result && <div className="hinweis arbeit" role="status">{job.result.count === 1 ? "Eine neue Nische wartet auf deine Entscheidung." : `${job.result.count} neue Nischen warten auf deine Entscheidung.`}<button className="knopf schmal" onClick={job.reset}>Schließen</button></div>}

      {niches.error && <div className="hinweis fehler" role="alert">{niches.error.message}<button className="knopf schmal" onClick={refresh}>Neu laden</button></div>}
      {niches.isLoading && <p className="leise">Lade Nischen …</p>}

      {niches.data?.length === 0 && !job.running && (
        <div className="karte leer">
          <h2>Noch keine Nischen</h2>
          <p className="leise">Lass dir Nischen vorschlagen oder beschreibe selbst eine in Stichpunkten. Du entscheidest danach, welche freigegeben werden.</p>
          <button className="knopf haupt" onClick={() => setDialog("generate")}>Nischen vorschlagen lassen</button>
        </div>
      )}

      {niches.data && niches.data.length > 0 && SECTIONS.map(({ status, title, empty }) => {
        const items = by(status);
        if (!items.length && !empty) return null;
        return (
          <section key={status} className="abschnitt">
            <header><span className={`punkt ${status}`} /><h2>{title}</h2><span className="leise">{items.length}</span></header>
            {items.length === 0 && <p className="leise">{empty}</p>}
            <div className="nischen">
              {items.map((n) => <NicheCard key={n.id} niche={n} onChanged={refresh} onEdit={() => setEditing(n)} onImprove={() => setImproving(n)} />)}
            </div>
          </section>
        );
      })}

      {rejected.length > 0 && (
        <details className="abschnitt eingeklappt">
          <summary><span className="punkt Rejected" /><h2>Abgelehnt</h2><span className="leise">{rejected.length}, zum Aufklappen tippen</span></summary>
          <div className="nischen">
            {rejected.map((n) => <NicheCard key={n.id} niche={n} onChanged={refresh} onEdit={() => setEditing(n)} onImprove={() => setImproving(n)} />)}
          </div>
        </details>
      )}

      {dialog === "generate" && <GenerateDialog onClose={() => setDialog("")}
        onStart={(count) => start(count === 1 ? "Die KI schreibt eine Nische." : `Die KI schreibt ${count} Nischen.`, () => api.generateNiches(id, count))} />}
      {dialog === "brief" && <BriefDialog onClose={() => setDialog("")}
        onStart={(brief) => start("Die KI baut deine Nische aus.", () => api.nicheFromBrief(id, brief))} />}
      {editing && <NicheEditor niche={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refresh(); }} />}
      {improving && <ImproveDialog niche={improving} onClose={() => setImproving(null)} onSaved={() => { setImproving(null); refresh(); }} />}
    </>
  );
}

function GenerateDialog({ onClose, onStart }: { onClose: () => void; onStart: (count: number) => void }) {
  const [count, setCount] = useState(3);
  return (
    <Dialog title="Nischen vorschlagen lassen" intro="Die KI schlägt vollständige Nischen mit Outfits, Orten, Szenen und Hooks vor. Nichts wird freigegeben, bevor du es prüfst."
      onClose={onClose}
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" onClick={() => onStart(count)}>{count === 1 ? "Eine Nische vorschlagen" : `${count} Nischen vorschlagen`}</button>
      </>}>
      <label className="feld"><span>Wie viele?</span>
        <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
          {[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
        </select>
        <small>Höchstens sechs pro Durchgang.</small></label>
    </Dialog>
  );
}

function BriefDialog({ onClose, onStart }: { onClose: () => void; onStart: (brief: string) => void }) {
  const [brief, setBrief] = useState("");
  const ready = brief.trim().length >= 10;
  return (
    <Dialog title="Nische aus Stichpunkten" intro="Schreib auf, was du dir vorstellst. Die KI hält sich an deine Vorgaben und füllt nur die Lücken."
      onClose={onClose}
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" disabled={!ready} onClick={() => onStart(brief.trim())}>Nische erstellen</button>
      </>}>
      <label className="feld"><span>Deine Stichpunkte</span>
        <textarea rows={7} value={brief} onChange={(e) => setBrief(e.target.value)} maxLength={4000} autoFocus
          placeholder={"z. B.\nTankstelle bei Nacht\nkurze Jeanskleider, Hotpants\nNeonlicht, nasser Asphalt"} />
        <small>Mindestens ein Satz.</small></label>
    </Dialog>
  );
}
