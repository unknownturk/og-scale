"use client";
import { useState } from "react";
import { Dialog } from "@/components/Dialog";
import { api } from "@/lib/api";
import type { Niche, NicheSpec, NicheStatus, Scenario } from "@/lib/types";
import { useJob } from "@/lib/useJob";

const SHOWN = 5;

function Pool({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <h4>{title}</h4>
      <ul>
        {items.slice(0, SHOWN).map((item, i) => <li key={i}>{item}</li>)}
        {items.length > SHOWN && <li className="mehr">und {items.length - SHOWN} weitere</li>}
      </ul>
    </div>
  );
}

export function NicheCard({ niche, onChanged, onEdit, onImprove }: {
  niche: Niche;
  onChanged: () => void;
  onEdit: () => void;
  onImprove: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

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
  const setStatus = (status: NicheStatus) => run(() => api.setNicheStatus(niche.id, status));

  return (
    <article className={`karte nische ${niche.status}`}>
      <div className="nische-kopf">
        <div>
          <h3>{niche.name}</h3>
          {niche.styleVibe && <p className="leise">{niche.styleVibe}</p>}
        </div>
        <div className="vorrat" title="Outfits mal Orte: so viele verschiedene Bilder sind möglich">
          <b>{niche.outfits.length}</b><i>×</i><b>{niche.backgrounds.length}</b>
          <span>= {niche.outfits.length * niche.backgrounds.length} Kombinationen</span>
        </div>
      </div>

      {niche.status !== "Rejected" && (
        <>
          <div className="pools">
            <Pool title="Outfits" items={niche.outfits} />
            <Pool title="Orte" items={niche.backgrounds} />
          </div>
          {niche.hooks[0] && <p className="hook">{niche.hooks[0]}</p>}
          {(niche.dressCode === "authentic" || niche.nsfwLevel !== "sfw") && (
            <div className="marken">
              {niche.dressCode === "authentic" && <span className="marke-klein">Echte Berufskleidung</span>}
              {niche.nsfwLevel !== "sfw" && <span className="marke-klein">{niche.nsfwLevel === "spicy" ? "Spicy" : "NSFW"}</span>}
            </div>
          )}
        </>
      )}

      {error && <div className="hinweis fehler" role="alert">{error}</div>}

      <div className="aktionen">
        {niche.status === "Proposed" && <>
          <button className="knopf haupt schmal" disabled={busy} onClick={() => setStatus("Approved")}>Freigeben</button>
          <button className="knopf schmal" disabled={busy} onClick={() => setStatus("Rejected")}>Ablehnen</button>
        </>}
        {niche.status === "Approved" && <button className="knopf schmal" disabled={busy} onClick={() => setStatus("Proposed")}>Freigabe zurücknehmen</button>}
        {niche.status === "Rejected" && <button className="knopf schmal" disabled={busy} onClick={() => setStatus("Proposed")}>Wieder prüfen</button>}
        <div className="rechts">
          {confirmDelete ? <>
            <span className="klein leise" style={{ alignSelf: "center" }}>Endgültig löschen?</span>
            <button className="knopf schmal gefahr" disabled={busy} onClick={() => run(() => api.deleteNiche(niche.id))}>Ja, löschen</button>
            <button className="knopf still schmal" onClick={() => setConfirmDelete(false)}>Nein</button>
          </> : <>
            {niche.status !== "Rejected" && <button className="knopf still schmal" onClick={onImprove}>Mit KI überarbeiten</button>}
            <button className="knopf still schmal" onClick={onEdit}>Bearbeiten</button>
            <button className="knopf still schmal" onClick={() => setConfirmDelete(true)}>Löschen</button>
          </>}
        </div>
      </div>
    </article>
  );
}

const lines = (text: string) => text.split("\n").map((l) => l.trim()).filter(Boolean);
const scenarioLine = (s: Scenario) => [s.name, s.setting, s.action].join(" | ");

export function NicheEditor({ niche, onClose, onSaved }: { niche: Niche; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(niche.name);
  const [styleVibe, setStyleVibe] = useState(niche.styleVibe);
  const [outfits, setOutfits] = useState(niche.outfits.join("\n"));
  const [backgrounds, setBackgrounds] = useState(niche.backgrounds.join("\n"));
  const [hooks, setHooks] = useState(niche.hooks.join("\n"));
  const [scenarios, setScenarios] = useState(niche.scenarios.map(scenarioLine).join("\n"));
  const [alwaysInclude, setAlwaysInclude] = useState(niche.alwaysInclude);
  const [authentic, setAuthentic] = useState(niche.dressCode === "authentic");
  const [nsfwLevel, setNsfwLevel] = useState(niche.nsfwLevel);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!lines(outfits).length || !lines(backgrounds).length) {
      setError("Eine Nische braucht mindestens ein Outfit und einen Ort.");
      return;
    }
    setBusy(true);
    setError("");
    // Szenen behalten ihre Zusatzangaben, wenn nur Name, Ort oder Aktion geändert wurden.
    const edited = lines(scenarios).map((line, i) => {
      const [n = "", setting = "", action = ""] = line.split("|").map((p) => p.trim());
      return { ...(niche.scenarios[i] ?? {}), name: n, setting, action };
    });
    try {
      await api.updateNiche(niche.id, {
        name: name.trim(), styleVibe: styleVibe.trim(), outfits: lines(outfits), backgrounds: lines(backgrounds),
        hooks: lines(hooks), scenarios: edited, alwaysInclude: alwaysInclude.trim(),
        dressCode: authentic ? "authentic" : "", nsfwLevel,
      });
      onSaved();
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Dialog title="Nische bearbeiten" onClose={onClose}
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" form="nische-form" disabled={busy}>{busy ? "Speichere …" : "Änderungen speichern"}</button>
      </>}>
      <form id="nische-form" className="formular" onSubmit={save}>
        <div className="zwei">
          <label className="feld"><span>Name</span>
            <input value={name} onChange={(e) => setName(e.target.value)} maxLength={120} required /></label>
          <label className="feld"><span>Stimmung und Licht</span>
            <input value={styleVibe} onChange={(e) => setStyleVibe(e.target.value)} /></label>
        </div>
        <label className="feld"><span>Outfits</span>
          <textarea rows={7} value={outfits} onChange={(e) => setOutfits(e.target.value)} />
          <small>Eines pro Zeile. Mehr Outfits bedeuten mehr Abwechslung im Content.</small></label>
        <label className="feld"><span>Orte</span>
          <textarea rows={4} value={backgrounds} onChange={(e) => setBackgrounds(e.target.value)} />
          <small>Einer pro Zeile.</small></label>
        <label className="feld"><span>Szenen</span>
          <textarea rows={4} value={scenarios} onChange={(e) => setScenarios(e.target.value)} />
          <small>Eine pro Zeile im Format: Name | Ort | Aktion</small></label>
        <label className="feld"><span>Hooks</span>
          <textarea rows={3} value={hooks} onChange={(e) => setHooks(e.target.value)} />
          <small>Einer pro Zeile.</small></label>
        <label className="feld"><span>Immer im Bild</span>
          <input value={alwaysInclude} onChange={(e) => setAlwaysInclude(e.target.value)} />
          <small>Etwas, das in jedem Bild dieser Nische vorkommen muss. Leer lassen, wenn es nichts gibt.</small></label>
        <div className="zwei">
          <label className="feld"><span>Freizügigkeit</span>
            <select value={nsfwLevel} onChange={(e) => setNsfwLevel(e.target.value as NicheSpec["nsfwLevel"])}>
              <option value="sfw">Jugendfrei</option><option value="spicy">Spicy</option><option value="nsfw">NSFW</option>
            </select></label>
          <label className="reihe" style={{ alignSelf: "end", minHeight: 42 }}>
            <input type="checkbox" checked={authentic} onChange={(e) => setAuthentic(e.target.checked)} />
            <span>Echte Berufskleidung</span></label>
        </div>
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
      </form>
    </Dialog>
  );
}

function Side({ title, spec, fresh }: { title: string; spec: Pick<NicheSpec, "outfits" | "backgrounds" | "hooks">; fresh?: boolean }) {
  return (
    <div className={fresh ? "neu" : undefined}>
      <h4>{title}</h4>
      <p className="klein leise">Outfits</p><ol>{spec.outfits.map((o, i) => <li key={i}>{o}</li>)}</ol>
      <p className="klein leise" style={{ marginTop: 10 }}>Orte</p><ol>{spec.backgrounds.map((o, i) => <li key={i}>{o}</li>)}</ol>
      {spec.hooks.length > 0 && <><p className="klein leise" style={{ marginTop: 10 }}>Hooks</p><ol>{spec.hooks.map((o, i) => <li key={i}>{o}</li>)}</ol></>}
    </div>
  );
}

export function ImproveDialog({ niche, onClose, onSaved }: { niche: Niche; onClose: () => void; onSaved: () => void }) {
  const [hint, setHint] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const job = useJob<{ proposal: NicheSpec }>();
  const proposal = job.result?.proposal;

  async function accept() {
    if (!proposal) return;
    setSaving(true);
    setSaveError("");
    try {
      await api.updateNiche(niche.id, proposal);
      onSaved();
    } catch (e) {
      setSaveError((e as Error).message);
      setSaving(false);
    }
  }

  return (
    <Dialog wide title={`„${niche.name}" mit KI überarbeiten`} onClose={onClose}
      intro={proposal ? "Vergleiche beide Fassungen. Gespeichert wird erst, wenn du den Vorschlag übernimmst." : "Die KI schreibt die Nische neu. Deine jetzige Fassung bleibt, bis du den Vorschlag übernimmst."}
      footer={proposal ? <>
        <button className="knopf still" onClick={onClose}>Alte Fassung behalten</button>
        <button className="knopf" onClick={job.reset} disabled={saving}>Neuer Versuch</button>
        <button className="knopf haupt" onClick={accept} disabled={saving}>{saving ? "Speichere …" : "Vorschlag übernehmen"}</button>
      </> : <>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" disabled={job.running} onClick={() => job.track(() => api.improveNiche(niche.id, hint))}>
          {job.running ? "KI schreibt …" : "Vorschlag erstellen"}</button>
      </>}>
      {proposal ? (
        <div className="formular">
          <div className="vergleich">
            <Side title="Jetzt" spec={niche} />
            <Side title="Vorschlag" spec={proposal} fresh />
          </div>
          {saveError && <div className="hinweis fehler" role="alert">{saveError}</div>}
        </div>
      ) : (
        <div className="formular">
          <label className="feld"><span>Was soll anders werden?</span>
            <textarea value={hint} onChange={(e) => setHint(e.target.value)} maxLength={1000} disabled={job.running}
              placeholder="z. B. mehr Outfits für draußen, weniger Sportkleidung" />
            <small>Kannst du leer lassen. Dann schreibt die KI die Nische frei neu.</small></label>
          {job.running && <div className="hinweis arbeit"><span className="reihe"><span className="puls" />Die KI schreibt. Das dauert bis zu zwei Minuten.</span></div>}
          {job.error && <div className="hinweis fehler" role="alert">{job.error}</div>}
        </div>
      )}
    </Dialog>
  );
}
