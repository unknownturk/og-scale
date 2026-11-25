"""AliRemote: Accounts auf Handys, Kurs wählen, Plan bauen, Reels zuordnen.

Hier wird nur geplant. Gestartet wird ausschließlich in executor.py.
"""

import hashlib
import json
import re
import uuid
from datetime import timedelta

from sqlalchemy import select

from .. import jobs, settings
from ..store import CONTENT, MODELS, NICHES, NotFound, get_store
from . import courses
from .client import AliError, AliUncertain, get_client
from .models import Account, Flag, Media, PhoneLock, Slot, now

OPEN = ("planned", "dispatching", "running")
NEEDS_YOU = ("uncertain", "failed", "missed")
STOP = "stop"

_DEFAULT_CAPTIONS = (
    "Ein kleiner Moment für deinen Feed. Wie ist dein Tag?",
    "Ein bisschen gute Laune für deinen Tag.",
    "Was steht heute bei dir an?",
)


class AliPlanError(ValueError):
    pass


def _id(prefix):
    return prefix + uuid.uuid4().hex[:14]


# --- Not-Stopp ---------------------------------------------------------------
def stopped(s=None):
    def read(session):
        row = session.get(Flag, STOP)
        return bool(row and row.value == "1")

    if s is not None:
        return read(s)
    with jobs.session() as session:
        return read(session)


def set_stopped(value: bool):
    with jobs.session() as s:
        row = s.get(Flag, STOP) or Flag(key=STOP)
        row.value = "1" if value else "0"
        s.merge(row)
        s.commit()
    return value


# --- Accounts ----------------------------------------------------------------
def add_account(username, niche_id, device_id):
    username = (username or "").strip().lstrip("@").lower()
    if not re.fullmatch(r"[a-z0-9._]{1,30}", username):
        raise AliPlanError("Das ist kein gültiger Instagram-Name")
    store = get_store()
    niche = store.get(NICHES, niche_id)
    if niche.get("status") != "Approved":
        raise AliPlanError("Diese Nische ist noch nicht freigegeben")
    try:
        device = next((d for d in get_client().devices() if d["id"] == device_id), None)
    except (AliError, AliUncertain) as exc:
        raise AliPlanError(f"Die Handys ließen sich nicht lesen: {exc}")
    if not device:
        raise AliPlanError("Dieses Handy gibt es bei AliRemote nicht")
    with jobs.session() as s:
        if s.scalar(select(Account).where(Account.username == username)):
            raise AliPlanError(f"@{username} gibt es schon")
        on_phone = list(s.scalars(select(Account).where(Account.device_id == device_id)))
        if len(on_phone) >= settings.MAX_ACCOUNTS_PER_PHONE:
            raise AliPlanError(f"Auf diesem Handy sind schon {settings.MAX_ACCOUNTS_PER_PHONE} Accounts")
        account = Account(id=_id("acc_"), username=username, model_id=niche["modelId"], niche_id=niche_id,
                          device_id=device_id, device_name=device["name"])
        s.add(account)
        s.commit()
        return account.id


def confirm_created(account_id, course):
    """Dein Klick »Account erstellt«: legt den Startzeitpunkt fest und baut den Plan
    des gewählten Kurses. Startet nichts — die Automatik schaltest du getrennt ein."""
    if course not in courses.COURSES:
        raise AliPlanError("Unbekannter Kurs")
    with jobs.session() as s:
        account = s.get(Account, account_id)
        if not account:
            raise NotFound(account_id)
        if account.created_at:
            raise AliPlanError("Dieser Account ist schon als erstellt bestätigt. Der Startzeitpunkt wird nicht zurückgesetzt.")
        if course == "native_7" and not account.native_id:
            try:
                match = [n for n in get_client().native_accounts() if n["username"] == account.username]
            except (AliError, AliUncertain):
                match = []
            if match:
                account.native_id = match[0]["id"]
        account.created_at = now()
        account.course = course
        _build_slots(s, account)
        _assign_reels(s, account)
        s.commit()


def _build_slots(s, account):
    """Schritte des Kurses anlegen. Überschneidet sich ein Schritt mit einem anderen
    auf demselben Handy, rückt er in 10-Minuten-Schritten nach hinten."""
    taken = [(x.due - timedelta(minutes=x.before), x.busy_until)
             for x in s.scalars(select(Slot).where(Slot.device_id == account.device_id, Slot.status.in_(OPEN)))]
    for day, kind, number, due, minutes, before, after in courses.steps(account.course, account.opening_at or account.created_at):
        for _ in range(12):
            start, end = courses.span(due, minutes, before, after)
            if not any(start < b and a < end for a, b in taken):
                break
            due += timedelta(minutes=10)
        start, end = courses.span(due, minutes, before, after)
        taken.append((start, end))
        s.add(Slot(id=_id("slot_"), account_id=account.id, device_id=account.device_id, kind=kind, day=day, ordinal=number,
                   due=due, window_end=due + timedelta(minutes=20), busy_until=end, minutes=minutes, before=before, after=after))
    s.flush()


def _caption(niche, seed):
    hooks = [h for h in (niche.get("hooks") or []) if isinstance(h, str) and h.strip()] or list(_DEFAULT_CAPTIONS)
    return hooks[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % len(hooks)]


def _assign_reels(s, account):
    """Freie, freigegebene Reels der Nische auf die offenen Reel-Plätze verteilen.
    Ein Reel gehört danach genau diesem Account."""
    store = get_store()
    try:
        niche = store.get(NICHES, account.niche_id)
    except NotFound:
        return 0
    owned = {m.content_id for m in s.scalars(select(Media))}
    free = [c for c in store.list(CONTENT, {"nicheId": account.niche_id})
            if c.get("type") == "Reel" and c.get("status") == "Approved" and c.get("finalReel") and c["id"] not in owned]
    empty = list(s.scalars(select(Slot).where(Slot.account_id == account.id, Slot.kind == "reel", Slot.status == "planned",
                                                Slot.content_id == "").order_by(Slot.due)))
    count = 0
    for slot, content in zip(empty, free):
        s.add(Media(content_id=content["id"], account_id=account.id))
        slot.content_id = content["id"]
        slot.caption = _caption(niche, content["id"])
        count += 1
    s.flush()
    return count


def refill_all():
    """Neu freigegebene Reels einsortieren (vom Takt aufgerufen)."""
    with jobs.session() as s:
        total = sum(_assign_reels(s, a) for a in s.scalars(select(Account).where(Account.created_at.isnot(None))))
        s.commit()
        return total


def set_armed(account_id, armed: bool):
    with jobs.session() as s:
        account = s.get(Account, account_id)
        if not account:
            raise NotFound(account_id)
        if armed and not account.created_at:
            raise AliPlanError("Bestätige zuerst, dass der Account erstellt ist")
        if armed and not get_client().configured():
            raise AliPlanError("AliRemote ist nicht verbunden (ALIREMOTE_TOKEN fehlt)")
        account.armed = armed
        if armed:
            account.note = ""
            slots = list(s.scalars(select(Slot).where(Slot.account_id == account_id)))
            if slots and all(x.status == "planned" for x in slots) and min(x.due for x in slots) < now():
                # Noch nichts gelaufen und der Plan liegt schon in der Vergangenheit: der Kurs
                # beginnt jetzt. Der Zeitpunkt »Account erstellt« bleibt unverändert.
                for slot in slots:
                    s.delete(slot)
                for media in s.scalars(select(Media).where(Media.account_id == account_id, Media.status != "used")):
                    s.delete(media)
                s.flush()
                account.opening_at = now()
                _build_slots(s, account)
                _assign_reels(s, account)
        s.commit()


def remove_account(account_id):
    with jobs.session() as s:
        account = s.get(Account, account_id)
        if not account:
            raise NotFound(account_id)
        busy = s.scalar(select(Slot).where(Slot.account_id == account_id, Slot.status.in_(("dispatching", "running", "uncertain"))))
        if busy:
            raise AliPlanError("Für diesen Account läuft noch etwas oder ist ungeklärt")
        for slot in s.scalars(select(Slot).where(Slot.account_id == account_id)):
            s.delete(slot)
        # Noch nicht gepostete Reels werden wieder frei; gepostete bleiben vergeben.
        for media in s.scalars(select(Media).where(Media.account_id == account_id, Media.status != "used")):
            s.delete(media)
        s.delete(account)
        s.commit()


# --- Deine Entscheidungen zu einzelnen Schritten -------------------------------
def resolve(slot_id, outcome):
    """Ungeklärten Schritt abschließen, nachdem du am Handy nachgesehen hast.
    outcome: "happened" (ist gelaufen) | "not_happened" (ist nicht gelaufen)."""
    with jobs.session() as s:
        slot = s.get(Slot, slot_id)
        if not slot:
            raise NotFound(slot_id)
        if slot.status != "uncertain":
            raise AliPlanError("Dieser Schritt ist nicht ungeklärt")
        slot.finished_at = now()
        if outcome == "happened":
            slot.status = "posted" if slot.kind == "reel" else "done"
            slot.detail = "Von dir bestätigt"
            if slot.kind == "reel":
                media = s.get(Media, slot.content_id)
                if media:
                    media.status = "used"
        else:
            slot.status = "failed"
            slot.detail = "Von dir geprüft: nicht gelaufen"
        lock = s.get(PhoneLock, slot.device_id)
        if lock and lock.slot_id == slot.id:
            s.delete(lock)
        s.commit()


def replan(slot_id):
    """Einen gescheiterten oder verpassten Schritt in fünf Minuten neu ansetzen.
    Nie für ungeklärte Schritte: die könnten schon gepostet haben."""
    with jobs.session() as s:
        slot = s.get(Slot, slot_id)
        if not slot:
            raise NotFound(slot_id)
        if slot.status not in ("failed", "missed"):
            raise AliPlanError("Nur gescheiterte oder verpasste Schritte lassen sich neu ansetzen")
        due = now() + timedelta(minutes=5)
        _, end = courses.span(due, slot.minutes, slot.before, slot.after)
        slot.due, slot.window_end, slot.busy_until = due, due + timedelta(minutes=20), end
        slot.status, slot.run_id, slot.dispatch_key, slot.detail, slot.evidence = "planned", "", "", "", ""
        slot.started_at = slot.finished_at = None
        s.commit()


def skip(slot_id):
    with jobs.session() as s:
        slot = s.get(Slot, slot_id)
        if not slot:
            raise NotFound(slot_id)
        if slot.status not in ("planned", "failed", "missed"):
            raise AliPlanError("Dieser Schritt lässt sich nicht mehr überspringen")
        slot.status, slot.detail, slot.finished_at = "cancelled", "Von dir übersprungen", now()
        if slot.kind == "reel" and slot.content_id:
            media = s.get(Media, slot.content_id)
            if media and media.status != "used":
                s.delete(media)  # das Reel wird wieder frei
            slot.content_id = ""
        s.commit()


# --- Ansicht -------------------------------------------------------------------
def _slot_view(slot):
    return {"id": slot.id, "kind": slot.kind, "day": slot.day, "ordinal": slot.ordinal, "due": slot.due.isoformat(),
            "status": slot.status, "detail": slot.detail, "minutes": slot.minutes, "contentId": slot.content_id,
            "caption": slot.caption, "hasReel": bool(slot.content_id), "inVault": bool(slot.vault_id)}


def overview():
    store = get_store()
    models = {m["id"]: m["name"] for m in store.list(MODELS)}
    niches = {n["id"]: n["name"] for n in store.list(NICHES)}
    client = get_client()
    devices, problem = [], ""
    if client.configured():
        try:
            devices = client.devices()
        except (AliError, AliUncertain) as exc:
            problem = f"Die Handys ließen sich nicht lesen: {exc}"
    with jobs.session() as s:
        accounts = []
        for account in s.scalars(select(Account).order_by(Account.added_at)):
            slots = list(s.scalars(select(Slot).where(Slot.account_id == account.id).order_by(Slot.due)))
            free = sum(1 for x in slots if x.kind == "reel" and x.status == "planned" and x.content_id)
            waiting = sum(1 for x in slots if x.kind == "reel" and x.status == "planned" and not x.content_id)
            accounts.append({
                "id": account.id, "username": account.username, "modelId": account.model_id,
                "modelName": models.get(account.model_id, ""), "nicheName": niches.get(account.niche_id, ""),
                "deviceId": account.device_id, "deviceName": account.device_name, "course": account.course,
                "courseName": courses.COURSES.get(account.course, {}).get("name", ""),
                "createdAt": account.created_at.isoformat() if account.created_at else None,
                "armed": bool(account.armed), "note": account.note or "",
                "reelsReady": free, "reelsMissing": waiting,
                "posted": sum(1 for x in slots if x.status == "posted"),
                "slots": [_slot_view(x) for x in slots],
            })
        return {
            "connected": client.configured(), "provider": client.name, "problem": problem, "stopped": stopped(s),
            "devices": devices, "accounts": accounts,
            "courses": [{"id": key, **value} for key, value in courses.COURSES.items()],
            "maxPerPhone": settings.MAX_ACCOUNTS_PER_PHONE,
        }


def evidence_text(data):
    return json.dumps(data, ensure_ascii=False)[:2000]
