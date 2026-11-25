"use client";
import { useMemo, useState } from "react";
import useSWR from "swr";
import { Dialog } from "@/components/Dialog";
import { api, fetcher } from "@/lib/api";
import type { AliAccount, AliOverview, AliSlot, Model, Niche } from "@/lib/types";

const KIND: Record<AliSlot["kind"], string> = { warmup: "Warm-up", native_warmup: "Warm-up", reel: "Reel", status: "Konto-Check" };
const STATE: Record<AliSlot["status"], string> = {
  planned: "geplant", dispatching: "startet", running: "läuft", done: "erledigt", posted: "gepostet",
  failed: "gescheitert", uncertain: "ungeklärt", missed: "verpasst", cancelled: "übersprungen",
};
const NEEDS_YOU: AliSlot["status"][] = ["uncertain", "failed", "missed"];

const clock = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Berlin" });
const dayName = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", timeZone: "Europe/Berlin" });
const dayKey = (iso: string) => new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Berlin" }).format(new Date(iso));

export default function AliRemotePage() {
  const { data, error, mutate } = useSWR<AliOverview>("/ali", fetcher, { refreshInterval: 15000 });
  const [adding, setAdding] = useState(false);
  const [starting, setStarting] = useState<AliAccount | null>(null);
  const [failure, setFailure] = useState("");

  async function act(action: () => Promise<AliOverview>) {
    setFailure("");
    try {
      mutate(await action(), { revalidate: false });
    } catch (e) {
      setFailure((e as Error).message);
    }
  }

  const phones = useMemo(() => {
    const groups = new Map<string, { name: string; online: boolean | null; accounts: AliAccount[] }>();
    for (const d of data?.devices ?? []) groups.set(d.id, { name: d.name, online: d.online, accounts: [] });
    for (const a of data?.accounts ?? []) {
      if (!groups.has(a.deviceId)) groups.set(a.deviceId, { name: a.deviceName || a.deviceId, online: null, accounts: [] });
      groups.get(a.deviceId)!.accounts.push(a);
    }
    return [...groups.entries()].sort((x, y) => y[1].accounts.length - x[1].accounts.length);
  }, [data]);

  const open = (data?.accounts ?? []).flatMap((a) => a.slots.filter((s) => NEEDS_YOU.includes(s.status)).map((s) => ({ a, s })));
  const running = (data?.accounts ?? []).flatMap((a) => a.slots).filter((s) => s.status === "running" || s.status === "dispatching").length;
  const today = dayKey(new Date().toISOString());
  const postedToday = (data?.accounts ?? []).flatMap((a) => a.slots).filter((s) => s.status === "posted" && dayKey(s.due) === today).length;

  return (
    <>
      <div className="kopf">
        <div>
          <h1>AliRemote</h1>
          <p className="leise">Deine Instagram-Accounts auf den ferngesteuerten Handys. Der Hub plant Warm-ups und Reels und startet sie nur bei eingeschalteter Automatik.</p>
        </div>
        <div className="reihe">
          {data && <button className={`knopf ${data.stopped ? "haupt" : "gefahr"}`} onClick={() => act(() => api.aliStop(!data.stopped))}>
            {data.stopped ? "Not-Stopp aufheben" : "Not-Stopp"}</button>}
          <button className="knopf haupt" disabled={!data?.devices.length} onClick={() => setAdding(true)}>Account planen</button>
        </div>
      </div>

      {error && <div className="hinweis fehler" role="alert">{error.message}</div>}
      {failure && <div className="hinweis fehler" role="alert">{failure}<button className="knopf schmal" onClick={() => setFailure("")}>Schließen</button></div>}
      {data && !data.connected && <div className="hinweis info">AliRemote ist noch nicht verbunden. Trag dein Zugangs-Token in die Umgebung ein (ALIREMOTE_TOKEN).</div>}
      {data?.provider === "fake" && <div className="hinweis info">Testbetrieb mit nachgestellten Handys. Es wird nichts wirklich gepostet.</div>}
      {data?.problem && <div className="hinweis fehler" role="alert">{data.problem}</div>}
      {data?.stopped && <div className="hinweis fehler" role="status">Not-Stopp ist aktiv. Es startet nichts Neues; laufende Schritte werden noch zu Ende abgelesen.</div>}

      {data && data.accounts.length > 0 && (
        <div className="kennzahlen">
          <div className="karte"><b className="t-cyan">{running}</b><span>laufen gerade</span></div>
          <div className="karte"><b className="t-mint">{postedToday}</b><span>heute gepostet</span></div>
          <div className={`karte${open.length ? " braucht" : ""}`}><b className={open.length ? "t-gelb" : ""}>{open.length}</b><span>brauchen dich</span></div>
        </div>
      )}

      {open.length > 0 && (
        <section className="abschnitt">
          <header><span className="punkt c-Failed" /><h2>Brauchen dich</h2><span className="leise">{open.length}</span></header>
          <div className="nischen">
            {open.map(({ a, s }) => (
              <article key={s.id} className={`karte offen s-${s.status}`}>
                <div>
                  <h3>{KIND[s.kind]} von @{a.username} ist {STATE[s.status]}</h3>
                  <p className="leise">{dayName.format(new Date(s.due))}, {clock.format(new Date(s.due))} Uhr auf {a.deviceName}. {s.detail}</p>
                </div>
                <div className="reihe">
                  {s.status === "uncertain" ? <>
                    <button className="knopf schmal" onClick={() => act(() => api.aliResolve(s.id, "happened"))}>{s.kind === "reel" ? "Ist gepostet" : "Ist gelaufen"}</button>
                    <button className="knopf schmal" onClick={() => act(() => api.aliResolve(s.id, "not_happened"))}>Ist nicht gelaufen</button>
                  </> : <>
                    <button className="knopf haupt schmal" onClick={() => act(() => api.aliReplan(s.id))}>In 5 Minuten neu ansetzen</button>
                    <button className="knopf still schmal" onClick={() => act(() => api.aliSkip(s.id))}>Überspringen</button>
                  </>}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {data && data.accounts.length === 0 && data.connected && (
        <div className="karte leer">
          <h2>Noch kein Account</h2>
          <p className="leise">Plane einen Account auf einem Handy. Erstelle ihn danach von Hand auf dem Gerät und bestätige das hier, dann wählst du den Warm-up-Kurs.</p>
          <button className="knopf haupt" disabled={!data.devices.length} onClick={() => setAdding(true)}>Account planen</button>
        </div>
      )}

      {phones.map(([id, phone]) => (
        <section key={id} className="abschnitt">
          <header>
            <span className={`punkt ${phone.online === false ? "c-Rejected" : "c-Approved"}`} />
            <h2>{phone.name}</h2>
            <span className="leise">{phone.online === false ? "offline, " : ""}{phone.accounts.length} von {data?.maxPerPhone} Accounts</span>
          </header>
          {phone.accounts.length === 0 && <p className="leise">Noch kein Account auf diesem Handy.</p>}
          <div className="nischen">
            {phone.accounts.map((a) => <AccountCard key={a.id} account={a} stopped={!!data?.stopped} act={act} onStart={() => setStarting(a)} />)}
          </div>
        </section>
      ))}

      {adding && data && <AddDialog overview={data} onClose={() => setAdding(false)} onDone={(next) => { setAdding(false); mutate(next, { revalidate: false }); }} />}
      {starting && data && <CourseDialog account={starting} courses={data.courses} onClose={() => setStarting(null)}
        onDone={(next) => { setStarting(null); mutate(next, { revalidate: false }); }} />}
    </>
  );
}

function AccountCard({ account: a, stopped, act, onStart }: {
  account: AliAccount; stopped: boolean; act: (run: () => Promise<AliOverview>) => void; onStart: () => void;
}) {
  const [confirm, setConfirm] = useState(false);
  const days = useMemo(() => {
    const map = new Map<string, AliSlot[]>();
    for (const s of a.slots) map.set(dayKey(s.due), [...(map.get(dayKey(s.due)) ?? []), s]);
    return [...map.entries()];
  }, [a.slots]);
  const next = a.slots.find((s) => s.status === "planned");

  return (
    <article className={`karte konto${a.armed ? " an" : ""}`}>
      <div className="nische-kopf">
        <div>
          <h3>@{a.username}</h3>
          <p className="leise">{a.modelName}, {a.nicheName}{a.courseName ? `, Kurs „${a.courseName}"` : ""}</p>
        </div>
        {a.createdAt && (
          <div className="vorrat" title="Freigegebene Reels, die diesem Account schon zugeordnet sind">
            <b>{a.reelsReady}</b><span>{a.reelsReady === 1 ? "Reel im Vorrat" : "Reels im Vorrat"}{a.reelsMissing > 0 ? `, ${a.reelsMissing} Plätze noch leer` : ""}</span>
          </div>
        )}
      </div>

      {!a.createdAt && <p>Erstelle <b>@{a.username}</b> jetzt von Hand auf {a.deviceName}. Wenn der Account steht, bestätige es hier und wähle den Warm-up-Kurs.</p>}
      {a.note && <div className="hinweis fehler">{a.note}</div>}
      {a.createdAt && !a.armed && !a.note && <div className="hinweis info">Der Plan steht, aber die Automatik ist aus. Solange startet nichts.</div>}
      {a.armed && next && <p className="leise">Als Nächstes: {KIND[next.kind]} am {dayName.format(new Date(next.due))} um {clock.format(new Date(next.due))} Uhr{stopped ? " (angehalten durch Not-Stopp)" : ""}.{next.detail ? ` ${next.detail}.` : ""}</p>}

      {days.length > 0 && (
        <div className="lauf" role="list" aria-label="Plan">
          {days.map(([key, slots]) => (
            <div key={key} className="lauf-tag" role="listitem">
              <span className="lauf-datum">{dayName.format(new Date(slots[0].due))}</span>
              <div className="lauf-schritte">
                {slots.map((s) => (
                  <span key={s.id} className={`schritt k-${s.kind} s-${s.status}${s.kind === "reel" && s.status === "planned" && !s.hasReel ? " leer" : ""}`}
                    title={`${KIND[s.kind]}, ${clock.format(new Date(s.due))} Uhr, ${STATE[s.status]}${s.detail ? `: ${s.detail}` : ""}${s.kind === "reel" && s.status === "planned" && !s.hasReel ? " (noch kein Reel)" : ""}`}>
                    {clock.format(new Date(s.due))}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
      {days.length > 0 && <p className="legende klein leise"><i className="schritt k-warmup" />Warm-up<i className="schritt k-reel" />Reel<i className="schritt k-reel leer" />Reel fehlt noch<i className="schritt k-status" />Konto-Check</p>}

      <div className="aktionen">
        {!a.createdAt && <button className="knopf haupt schmal" onClick={onStart}>Account erstellt</button>}
        {a.createdAt && (a.armed
          ? <button className="knopf schmal" onClick={() => act(() => api.aliArmed(a.id, false))}>Automatik pausieren</button>
          : <button className="knopf haupt schmal" onClick={() => act(() => api.aliArmed(a.id, true))}>Automatik starten</button>)}
        <div className="rechts">
          {confirm ? <>
            <span className="klein leise" style={{ alignSelf: "center" }}>Account und Plan entfernen?</span>
            <button className="knopf schmal gefahr" onClick={() => act(() => api.aliRemove(a.id))}>Ja, entfernen</button>
            <button className="knopf still schmal" onClick={() => setConfirm(false)}>Nein</button>
          </> : <button className="knopf still schmal" onClick={() => setConfirm(true)}>Entfernen</button>}
        </div>
      </div>
    </article>
  );
}

function CourseDialog({ account, courses, onClose, onDone }: {
  account: AliAccount; courses: AliOverview["courses"]; onClose: () => void; onDone: (next: AliOverview) => void;
}) {
  const [course, setCourse] = useState(courses[0]?.id ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Dialog title={`@${account.username} ist erstellt`} onClose={onClose}
      intro="Mit deiner Bestätigung beginnt der Kurs zu zählen. Es startet noch nichts: die Automatik schaltest du danach selbst ein."
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" disabled={busy || !course} onClick={async () => {
          setBusy(true);
          setError("");
          try {
            onDone(await api.aliCreated(account.id, course));
          } catch (e) {
            setError((e as Error).message);
            setBusy(false);
          }
        }}>{busy ? "Baue Plan …" : "Bestätigen und Plan bauen"}</button>
      </>}>
      <fieldset className="kurse">
        <legend>Welcher Warm-up-Kurs?</legend>
        {courses.map((c) => (
          <label key={c.id} className={`kurs${course === c.id ? " gewaehlt" : ""}`}>
            <input type="radio" name="kurs" value={c.id} checked={course === c.id} onChange={() => setCourse(c.id)} />
            <span><b>{c.name}</b><span className="leise">{c.summary}</span></span>
          </label>
        ))}
      </fieldset>
      {error && <div className="hinweis fehler" role="alert" style={{ marginTop: 14 }}>{error}</div>}
    </Dialog>
  );
}

function AddDialog({ overview, onClose, onDone }: { overview: AliOverview; onClose: () => void; onDone: (next: AliOverview) => void }) {
  const models = useSWR<Model[]>("/models", fetcher);
  const [modelId, setModelId] = useState("");
  const current = modelId || models.data?.[0]?.id || "";
  const niches = useSWR<Niche[]>(current ? `/models/${current}/niches` : null, fetcher);
  const approved = (niches.data ?? []).filter((n) => n.status === "Approved");
  const [nicheId, setNicheId] = useState("");
  const niche = approved.find((n) => n.id === nicheId) ?? approved[0];
  const count = (id: string) => overview.accounts.filter((a) => a.deviceId === id).length;
  const free = overview.devices.filter((d) => count(d.id) < overview.maxPerPhone);
  const [deviceId, setDeviceId] = useState("");
  const device = free.find((d) => d.id === deviceId) ?? free[0];
  const [username, setUsername] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!niche || !device) return;
    setBusy(true);
    setError("");
    try {
      onDone(await api.aliAddAccount(username, niche.id, device.id));
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <Dialog title="Account planen" intro="Leg fest, welcher Account auf welchem Handy entstehen soll. Erstellt wird er danach von dir am Gerät." onClose={onClose}
      footer={<>
        <button className="knopf still" onClick={onClose}>Abbrechen</button>
        <button className="knopf haupt" form="konto-form" disabled={busy || !niche || !device || !username.trim()}>{busy ? "Speichere …" : "Account planen"}</button>
      </>}>
      <form id="konto-form" className="formular" onSubmit={save}>
        <div className="zwei">
          <label className="feld"><span>Model</span>
            <select value={current} onChange={(e) => { setModelId(e.target.value); setNicheId(""); }}>
              {models.data?.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
          <label className="feld"><span>Nische</span>
            <select value={niche?.id ?? ""} onChange={(e) => setNicheId(e.target.value)} disabled={!approved.length}>
              {approved.length === 0 && <option value="">Keine freigegebene Nische</option>}
              {approved.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
        </div>
        <label className="feld"><span>Handy</span>
          <select value={device?.id ?? ""} onChange={(e) => setDeviceId(e.target.value)} disabled={!free.length}>
            {free.length === 0 && <option value="">Alle Handys sind voll</option>}
            {free.map((d) => <option key={d.id} value={d.id}>{d.name}{d.online ? "" : " (offline)"}, {count(d.id)} von {overview.maxPerPhone} belegt</option>)}</select></label>
        <label className="feld"><span>Instagram-Name</span>
          <input value={username} onChange={(e) => setUsername(e.target.value)} maxLength={31} placeholder="z. B. lena.tanke" autoCapitalize="none" />
          <small>Der Name, den du beim Erstellen auf dem Handy vergibst.</small></label>
        {error && <div className="hinweis fehler" role="alert">{error}</div>}
      </form>
    </Dialog>
  );
}
