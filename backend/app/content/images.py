"""Carousels und Fotos erzeugen.

Jeder Content-Datensatz hat „Plätze" (einen pro Bild). Für jeden Platz liegt
eine Quittung im Datensatz: Phase, Auftragsnummer, Ergebnis. Dadurch gilt:

- Fertige Bilder werden sofort gespeichert. Scheitert Bild 8, bleiben 1–7.
- Nach einem Neustart wird derselbe Auftrag weiter abgefragt, nie neu bezahlt.
- Ist unklar, ob der Anbieter einen Auftrag angenommen hat, wird nichts
  automatisch wiederholt. Erst »Erneut versuchen« gibt den Platz wieder frei.
"""

import random
import time

from .. import jobs, settings
from ..media import MediaError, SubmissionUncertain, get_provider
from ..store import CONTENT, MODELS, NICHES, get_store
from . import prompts

UNCERTAIN = "Unklar, ob der Anbieter den Auftrag angenommen hat"


class ContentError(ValueError):
    pass


# --- Anlegen ----------------------------------------------------------------
def create(niche_id, kind, count, mode="niche", style_intensity=60):
    """Legt die Datensätze an und startet je einen Auftrag. kind: carousel | photos."""
    if not 1 <= count <= settings.MAX_IMAGES_PER_REQUEST:
        raise ContentError(f"Zwischen 1 und {settings.MAX_IMAGES_PER_REQUEST} Bilder pro Auftrag")
    store = get_store()
    niche = store.get(NICHES, niche_id)
    if niche.get("status") != "Approved":
        raise ContentError("Diese Nische ist noch nicht freigegeben")
    model = store.get(MODELS, niche["modelId"])
    if not model.get("referenceImages"):
        raise ContentError("Dieses Model hat noch keine Referenzfotos. Lade zuerst welche hoch.")
    if not get_provider().configured():
        raise ContentError("Die Bild-Erzeugung ist nicht eingerichtet (KIE_API_KEY fehlt)")

    number = len(store.list(CONTENT, {"modelId": model["id"]})) + 1
    plans = [("Carousel", count)] if kind == "carousel" else [("Photo", 1)] * count
    created = []
    for offset, (content_type, slots) in enumerate(plans):
        label = "Carousel" if content_type == "Carousel" else "Foto"
        record = store.create(CONTENT, {
            "title": f"{label} {number + offset}: {niche['name']}",
            "modelId": model["id"], "nicheId": niche["id"], "type": content_type,
            "status": "Working", "step": "images", "mode": mode, "error": "", "images": [],
            "prompt": "",
            "tasks": {"intensity": style_intensity, "slots": [{"phase": "new"} for _ in range(slots)]},
        })
        jobs.start("content_images", {"contentId": record["id"]}, subject=record["id"])
        created.append(record)
    return created


def retry(content_id):
    """Fehlende Bilder noch einmal versuchen. Gibt unklare Plätze ausdrücklich frei."""
    store = get_store()
    content = store.get(CONTENT, content_id)
    if content["type"] not in ("Carousel", "Photo"):
        raise ContentError("Nur für Bilder")
    if jobs.active(subject=content_id):
        raise ContentError("Dafür läuft bereits ein Auftrag")
    tasks = content.get("tasks") or {}
    for slot in tasks.get("slots", []):
        if not slot.get("url") and not slot.get("taskId"):
            slot.clear()
            slot["phase"] = "new"
    store.update(CONTENT, content_id, {"status": "Working", "error": "", "tasks": tasks})
    return jobs.start("content_images", {"contentId": content_id}, subject=content_id)


# --- Prompt -----------------------------------------------------------------
def _look(niche):
    outfits = prompts.varied_outfits(niche.get("outfits"), niche.get("nsfwLevel"))
    backgrounds = [b for b in (niche.get("backgrounds") or []) if b]
    return random.choice(outfits), (random.choice(backgrounds) if backgrounds else None)


def _prompt_for(index, content, niche, model, look):
    """Prompt-Kette für einen Platz: gewünschter Prompt, dann zwei mildere Fassungen,
    falls die Moderation des Anbieters ablehnt."""
    carousel = content["type"] == "Carousel"
    mode = content.get("mode") or "niche"
    nsfw = (niche.get("nsfwLevel") or "sfw").lower()
    outfit, background = look if carousel else _look(niche)  # Carousel = ein Look, Fotos = je ein eigener
    text = prompts.build_carousel_base_prompt(model["name"], outfit=outfit, background=background, mode=mode, nsfw_level=nsfw)
    scenarios = [s for s in (niche.get("scenarios") or []) if s.get("action")]
    if scenarios and (index > 0 or not carousel):
        text += f", she is {scenarios[index % len(scenarios)]['action']}"
    text += prompts.body_clause(model.get("bodyType"))
    text += prompts.market_cue(prompts.effective_market(niche.get("market"), model.get("language")), index)
    if niche.get("dressCode") == "authentic":
        text += " Authentic, realistic real-life uniform with accurate details." + prompts.name_tag_clause(model["name"])
    if niche.get("alwaysInclude"):
        text = f"{text}. MANDATORY: {niche['alwaysInclude']}"
    intensity = (content.get("tasks") or {}).get("intensity", 60)
    text = prompts.apply_style(text, intensity, niche.get("name", "model"), mode=mode) + prompts.IDENTITY_LOCK
    return [
        prompts.sanitize_prompt(text, nsfw),
        prompts.fallback_prompt(model["name"], outfit, background, nsfw),
        prompts.safe_fallback_prompt(model["name"]),
    ]


# --- Ausführen --------------------------------------------------------------
def _save(content_id, tasks, **fields):
    urls = [s["url"] for s in tasks["slots"] if s.get("url")]
    return get_store().update(CONTENT, content_id, {"tasks": tasks, "images": urls, **fields})


def _submit(slot, index, content, niche, model, references, tasks):
    """Einen Platz beauftragen. Die Quittung wird VOR dem Senden geschrieben."""
    chain = slot.get("prompts") or _prompt_for(index, content, niche, model, tasks["look"])
    slot["prompts"] = chain
    slot["phase"] = "submitting"
    _save(content["id"], tasks)
    try:
        task_id = get_provider().submit_image(chain[slot.get("attempt", 0)], references, aspect_ratio="4:5", resolution="2K")
    except SubmissionUncertain:
        slot["error"] = UNCERTAIN
        _save(content["id"], tasks)
        return
    except MediaError as exc:
        slot.update(phase="failed", error=str(exc))
        _save(content["id"], tasks)
        return
    slot.update(phase="submitted", taskId=task_id)
    slot.pop("error", None)
    _save(content["id"], tasks)


def _settle(slot, result):
    """Ergebnis einer Abfrage in die Quittung schreiben. True = Platz ist erledigt."""
    if result["state"] == "waiting":
        return False
    if result["state"] == "success":
        slot.update(phase="done", url=result["url"])
        slot.pop("error", None)
        return True
    slot.pop("taskId", None)
    error = result.get("error") or "Fehlgeschlagen"
    if prompts.is_review_error(error) and slot.get("attempt", 0) < 2:
        slot["attempt"] = slot.get("attempt", 0) + 1  # mildere Fassung, neuer Auftrag
        slot["phase"] = "new"
    else:
        slot.update(phase="failed", error=error)
    return True


@jobs.handler("content_images", resume=True)
def run(payload):
    store = get_store()
    content = store.get(CONTENT, payload["contentId"])
    niche = store.get(NICHES, content["nicheId"])
    model = store.get(MODELS, content["modelId"])
    provider = get_provider()
    tasks = content.get("tasks") or {"slots": []}
    slots = tasks["slots"]
    tasks.setdefault("look", list(_look(niche)))
    identity = list(model.get("referenceImages") or [])[:3]
    carousel = content["type"] == "Carousel"
    deadline = time.monotonic() + settings.IMAGE_WAIT_SECONDS

    def ready(index):
        # Im Carousel richten sich alle Bilder nach dem ersten (gleicher Look).
        return not carousel or index == 0 or bool(slots[0].get("url")) or slots[0].get("phase") == "failed"

    while True:
        for index, slot in enumerate(slots):
            if slot.get("phase") == "new" and ready(index):
                first = [slots[0]["url"]] if carousel and index > 0 and slots[0].get("url") else []
                _submit(slot, index, content, niche, model, identity + first, tasks)
        waiting = [s for s in slots if s.get("taskId") and not s.get("url")]
        if not waiting and not any(s.get("phase") == "new" and ready(i) for i, s in enumerate(slots)):
            break
        if time.monotonic() > deadline:
            break
        changed = False
        for slot in waiting:
            changed |= _settle(slot, provider.check(slot["taskId"]))
        if changed:
            _save(content["id"], tasks)
        else:
            time.sleep(settings.POLL_SECONDS)

    done = sum(1 for s in slots if s.get("url"))
    pending = [s for s in slots if s.get("taskId") and not s.get("url")]
    unclear = [s for s in slots if s.get("phase") == "submitting"]
    problems = []
    if pending:
        problems.append(f"{len(pending)} Bild(er) brauchen ungewöhnlich lange. »Erneut versuchen« fragt dieselben Aufträge weiter ab, ohne neu zu bezahlen.")
    if unclear:
        problems.append(f"Bei {len(unclear)} Bild(ern) ist unklar, ob Kie den Auftrag angenommen hat. »Erneut versuchen« sendet sie neu.")
    failed = [s for s in slots if s.get("phase") == "failed"]
    if failed:
        problems.append(f"{len(failed)} Bild(er) fehlgeschlagen: {failed[0].get('error', '')}")
    # Offene oder unklare Aufträge brauchen dich; sonst reicht ein fertiges Bild zur Prüfung.
    status = "Failed" if pending or unclear or not done else "Review"
    _save(content["id"], tasks, status=status, error=" ".join(problems),
          prompt=(slots[0].get("prompts") or [""])[0] if slots else "")
    return {"contentId": content["id"], "images": done, "missing": len(slots) - done}
