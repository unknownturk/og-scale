"""Der eine Ausführer: liefert Reels in den Tresor, startet fällige Schritte,
liest Quittungen. Läuft einmal pro Minute (tick).

Regeln:
- Nichts startet ohne eingeschaltete Automatik des Accounts; der Not-Stopp
  hält alles an (laufende Läufe werden weiter abgelesen, nichts Neues startet).
- Ein Handy macht eine Sache: Sperre je Handy, in der Datenbank.
- Vor jedem Start steht die Quittung (Zustand »dispatching« + Schlüssel) schon
  in der Datenbank. Geht die Antwort verloren, wird NIE von selbst neu gestartet:
  der Schritt wird »ungeklärt« und wartet auf dich.
- Ein grüner Lauf ist noch kein Post. »Gepostet« gilt nur mit passender Quittung.
"""

import hashlib
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .. import jobs, settings
from ..store import CONTENT, MODELS, NICHES, NotFound, get_store
from . import service
from .client import TERMINAL, AliError, AliUncertain, get_client
from .models import Account, Media, PhoneLock, Slot, now

BAD_ACCOUNT = {"logged_out": "ausgeloggt", "confirm_identity": "Instagram verlangt eine Bestätigung",
               "suspended": "gesperrt", "blocked": "blockiert"}


def _key(*parts):
    return "ogs:" + hashlib.sha256(":".join(str(p) for p in parts).encode()).hexdigest()[:40]


def _true(value):
    return value is True or value == "true"


# --- Quittung auswerten --------------------------------------------------------
def outcome(slot, account, run):
    """(zustand, text, daten). zustand: running | done | posted | failed | uncertain."""
    status = str(run.get("status", "")).lower()
    if status not in TERMINAL:
        return "running", "", None
    out = run.get("output") if isinstance(run.get("output"), dict) else {}
    devices = {step.get("device") for step in run.get("steps") or [] if step.get("device")}
    if out.get("phone"):
        devices.add(out["phone"])
    same = (devices <= {slot.device_id} and out.get("slot_id") == slot.id
            and str(out.get("account", "")).lstrip("@").lower() == account.username)
    ok = status in ("succeeded", "completed")
    if slot.kind == "status":
        state = out.get("account_status") or {"FINE": "fine", "LOGGED_OUT": "logged_out", "CONFIRM_ITS_YOU": "confirm_identity",
                                              "SUSPENDED": "suspended", "BLOCKED": "blocked"}.get(out.get("result_code"))
        if ok and same and state == "fine":
            return "done", "Konto in Ordnung", out
        if ok and same and state in BAD_ACCOUNT:
            return "failed", f"Konto {BAD_ACCOUNT[state]}", {**out, "accountProblem": state}
        return "failed", "Konto-Check ohne klares Ergebnis", out
    if slot.kind == "warmup":
        if ok and same and _true(out.get("session_done")) and str(out.get("minutes")) == str(slot.minutes):
            return "done", "Warm-up bestätigt", out
        return "failed", "Warm-up ohne passende Quittung beendet", out
    # Reel: Auch ein abgebrochener Lauf kann schon auf »Teilen« getippt haben.
    unverified = "SHARED_UNVERIFIED" in (str(out.get("status", "")).upper(), str(out.get("result_code", "")).upper())
    counted = True
    if "posts_before" in out or "posts_after" in out:
        try:
            counted = int(out["posts_after"]) > int(out["posts_before"])
        except (KeyError, TypeError, ValueError):
            counted = False
    if (ok and same and not unverified and out.get("video") == slot.vault_id and _true(out.get("posted"))
            and _true(out.get("verified")) and out.get("after_scroll") == "done" and counted):
        return "posted", "Gepostet und bestätigt", out
    return "uncertain", "Der Lauf ist beendet, aber der Post ist nicht bestätigt. Sieh am Handy nach.", out


def _native_outcome(slot, warmup):
    if warmup.get("running") or warmup.get("starting"):
        return "running", "", None
    sessions = warmup.get("sessions") or []
    if warmup.get("status") == "done" and not warmup.get("note") and warmup.get("sessions_done") == 1 and len(sessions) == 1 \
            and sessions[0].get("outcome") == "done":
        return "done", "Warm-up bestätigt", {"session": sessions[0].get("id")}
    if warmup.get("status") in ("done", "stopped", "paused") or warmup.get("note"):
        return "failed", f"Warm-up nicht abgeschlossen ({warmup.get('note') or warmup.get('status')})", warmup
    return "running", "", None


# --- Tresor ---------------------------------------------------------------------
def deliver_due(horizon_hours=24):
    """Reels, die bald dran sind, in den AliRemote-Tresor legen."""
    client, store = get_client(), get_store()
    with jobs.session() as s:
        soon = now() + timedelta(hours=horizon_hours)
        rows = list(s.execute(select(Slot, Account).join(Account, Account.id == Slot.account_id).where(
            Slot.kind == "reel", Slot.status == "planned", Slot.content_id != "", Slot.vault_id == "",
            Slot.due <= soon, Account.armed.is_(True))))
        for slot, account in rows:
            media = s.get(Media, slot.content_id)
            if not media or media.status == "failed":
                continue
            if media.status == "ready" and media.vault_id:
                slot.vault_id = media.vault_id
                s.commit()
                continue
            try:
                content = store.get(CONTENT, slot.content_id)
                url = (content.get("finalReel") or [""])[0]
                if not (url.startswith("https://") or (settings.ALLOW_PRIVATE_URLS and url.startswith("http://"))):
                    raise AliError("Das Reel hat keine öffentliche Adresse")
                model = store.get(MODELS, account.model_id)["name"]
                niche = store.get(NICHES, account.niche_id)["name"]
            except (NotFound, AliError) as exc:
                media.status, media.detail = "failed", str(exc) or "Reel nicht gefunden"
                slot.detail = f"Lieferung fehlgeschlagen: {media.detail}"
                s.commit()
                continue
            media.status, media.delivery_key = "delivering", _key("media", slot.content_id, account.id)
            s.commit()  # Quittung steht, bevor AliRemote die Datei holt
            try:
                folder = client.ensure_folder([model, niche, "Reels", account.username])
                vault_id = client.import_media(url, f"{account.username}-{slot.content_id}.mp4", folder, media.delivery_key)
                state = client.media(vault_id)
            except AliError as exc:
                media.status, media.detail = "failed", str(exc)
                slot.detail = f"Lieferung fehlgeschlagen: {exc}"
                s.commit()
                continue
            except AliUncertain:
                # Derselbe Schlüssel beim nächsten Takt: AliRemote legt die Datei nicht doppelt an.
                media.status = "assigned"
                slot.detail = "Der Tresor antwortet gerade nicht. Die Lieferung wird wiederholt."
                s.commit()
                continue
            if state and state["ready"] and not state["expired"]:
                media.status, media.vault_id, media.detail = "ready", vault_id, ""
                slot.vault_id, slot.detail = vault_id, ""
            else:
                media.status = "assigned"  # noch nicht bereit: nächster Takt fragt denselben Schlüssel
            s.commit()


# --- Starten ---------------------------------------------------------------------
def _inputs(slot, account):
    data = {"account": account.username, "slot_id": slot.id}
    if slot.kind == "warmup":
        data.update(rotate="no", minutes=slot.minutes, surface="reels", like_percent=0)
    elif slot.kind == "reel":
        data.update(rotate="no", video=slot.vault_id, scroll_before=slot.before, scroll_after=slot.after)
        if slot.caption and settings.ALI_SEND_CAPTION:
            data["caption"] = slot.caption
    return data


def _blocker(slot, account, s):
    """Warum ein fälliger Schritt (noch) nicht starten darf. None = darf."""
    if slot.kind == "reel":
        if not slot.content_id:
            return "Kein freigegebenes Reel im Vorrat"
        if not slot.vault_id:
            return slot.detail or "Das Reel ist noch nicht im Tresor"
        earlier = s.scalar(select(Slot).where(Slot.account_id == account.id, Slot.kind == "reel", Slot.due < slot.due,
                                              Slot.status == "uncertain"))
        if earlier:
            return "Ein früheres Reel dieses Accounts ist noch ungeklärt"
    if slot.kind == "native_warmup" and not account.native_id:
        return "Dieser Account ist in AliRemote nicht als Instagram-Konto hinterlegt"
    return None


def dispatch_due():
    client = get_client()
    started = 0
    with jobs.session() as s:
        if service.stopped(s):
            return 0
        moment = now()
        due = list(s.execute(select(Slot, Account).join(Account, Account.id == Slot.account_id).where(
            Slot.status == "planned", Slot.due <= moment, Account.armed.is_(True)).order_by(Slot.due)))
        seen_phones = set()
        for slot, account in due:
            if moment > slot.window_end:
                slot.status, slot.finished_at = "missed", moment
                slot.detail = _blocker(slot, account, s) or "Das Handy war im Zeitfenster belegt oder nicht erreichbar"
                s.commit()
                continue
            if slot.device_id in seen_phones:
                continue
            seen_phones.add(slot.device_id)
            blocker = _blocker(slot, account, s)
            if blocker:
                slot.detail = blocker
                s.commit()
                continue
            try:
                if not client.phone_free(slot.device_id):
                    slot.detail = "Das Handy ist gerade belegt"
                    s.commit()
                    continue
            except (AliError, AliUncertain):
                continue
            try:  # die Handy-Sperre: wer sie einfügen kann, darf starten
                with s.begin_nested():
                    s.add(PhoneLock(device_id=slot.device_id, slot_id=slot.id))
            except IntegrityError:
                continue
            slot.status, slot.started_at, slot.detail = "dispatching", moment, ""
            slot.dispatch_key = _key("run", slot.id, slot.due.isoformat())
            s.commit()  # Quittung steht vor dem Start
            try:
                if slot.kind == "native_warmup":
                    run_id = client.start_warmup(slot.device_id, account.native_id, slot.minutes, slot.dispatch_key)
                else:
                    automation = {"warmup": settings.ALI_WARMUP_AUTOMATION, "reel": settings.ALI_REEL_AUTOMATION,
                                  "status": settings.ALI_STATUS_AUTOMATION}[slot.kind]
                    run_id = client.start_run(automation, slot.device_id, _inputs(slot, account), slot.dispatch_key)
            except AliError as exc:  # sicher nicht gestartet
                slot.status, slot.finished_at, slot.detail = "failed", now(), f"AliRemote hat den Start abgelehnt: {exc}"
                s.delete(s.get(PhoneLock, slot.device_id))
                s.commit()
                continue
            except AliUncertain:
                slot.status = "uncertain"
                slot.detail = "Unklar, ob der Lauf gestartet ist. Sieh in AliRemote nach und entscheide hier."
                s.commit()
                continue
            slot.status, slot.run_id = "running", run_id
            s.commit()
            started += 1
    return started


# --- Ablesen ---------------------------------------------------------------------
def poll_running():
    client = get_client()
    with jobs.session() as s:
        rows = list(s.execute(select(Slot, Account).join(Account, Account.id == Slot.account_id).where(
            Slot.run_id != "", Slot.status.in_(("running", "uncertain")), Slot.finished_at.is_(None))))
        for slot, account in rows:
            try:
                if slot.kind == "native_warmup":
                    state, text, data = _native_outcome(slot, client.warmup(slot.run_id))
                else:
                    state, text, data = outcome(slot, account, client.run(slot.run_id))
            except (AliError, AliUncertain):
                continue  # nächster Takt
            if state == "running":
                if now() > slot.busy_until + timedelta(minutes=45):
                    slot.status = "uncertain"
                    slot.detail = "Der Lauf meldet sich nicht mehr. Sieh in AliRemote nach und entscheide hier."
                    s.commit()
                continue
            slot.status, slot.detail, slot.evidence = state, text, service.evidence_text(data)
            if state != "uncertain":
                slot.finished_at = now()
            if state == "posted":
                media = s.get(Media, slot.content_id)
                if media:
                    media.status = "used"
            if data and data.get("accountProblem"):
                account.armed = False
                account.note = f"Automatik pausiert: Konto {BAD_ACCOUNT[data['accountProblem']]}"
            lock = s.get(PhoneLock, slot.device_id)
            if lock and lock.slot_id == slot.id:  # der Lauf ist zu Ende: das Handy ist wieder frei
                s.delete(lock)
            s.commit()


def release_stale_locks():
    """Ungeklärter Start ohne Lauf-Nummer: das Handy nicht für immer blockieren.
    Der Schritt selbst bleibt ungeklärt und wird nie von selbst wiederholt."""
    client = get_client()
    with jobs.session() as s:
        for lock in list(s.scalars(select(PhoneLock))):
            slot = s.get(Slot, lock.slot_id)
            if slot is None:
                s.delete(lock)
            elif slot.status == "uncertain" and not slot.run_id and now() > slot.busy_until + timedelta(minutes=5):
                try:
                    if client.phone_free(slot.device_id):
                        s.delete(lock)
                except (AliError, AliUncertain):
                    pass
        s.commit()


def tick():
    """Ein Durchgang. Jeder Teil darf scheitern, ohne die anderen aufzuhalten."""
    if not get_client().configured():
        return
    for step in (poll_running, release_stale_locks, service.refill_all, deliver_due, dispatch_due):
        try:
            step()
        except Exception as exc:  # der Takt darf nie sterben
            print(f"[ali] {step.__name__}: {exc}")
