"""Motion-Reels: Vorlage -> Bild mit dem Model -> deine Freigabe -> Video.

    1. vorbereiten   Vorlage laden, erstes Bild auslesen, Video umrechnen
    2. Bild          Kie baut das erste Bild mit dem Model nach
       --- du gibst das Bild frei ---
    3. Video         Kling Motion-Control bewegt sie wie in der Vorlage
       --- du gibst das Reel frei ---

Jeder bezahlte Schritt hat eine Quittung im Datensatz (tasks.image / tasks.video).
Ein Neustart oder »Erneut versuchen« fragt denselben Auftrag weiter ab, statt neu
zu bezahlen.
"""

import random
import time

from .. import jobs, settings
from ..media import MediaError, SubmissionUncertain, get_provider
from ..store import CONTENT, MODELS, NICHES, get_store
from . import prompts, video
from .images import UNCERTAIN, ContentError

VIDEO_PROMPT = "Create a high-quality, cinematic video."


# Mehrere Fassungen derselben Vorlage (für mehrere Accounts): gleiche Pose, kleine
# Unterschiede in Licht und Stoff, damit keine zwei Accounts dasselbe Bild posten.
VARIANTS = (
    "Use neutral natural light with subtle fabric texture variation.",
    "Use subtly warmer natural light with small fabric fold differences.",
    "Use subtly cooler natural light with small fabric fold differences.",
)
VARIANT_RULES = (
    " Generate this account image independently from the references. {variation}"
    " These small variations must NOT change the source pose, gesture, camera angle, crop,"
    " subject placement or scene geometry. Keep the source framing 1:1; do not invent a new composition."
    " Preserve visible props, animals, furniture positions and interactions with them. Do not add unrelated props."
    " Change identity to the model in references 2 onward. Niche styling may change clothing and scene appearance,"
    " but the first reference remains the strict spatial template. No collage or duplicate panels."
)


def create(niche_id, sources, video_model="kling-3.0", label="", as_variants=False):
    """sources: Liste von Adressen (Video-Links oder schon hochgeladene Dateien).
    as_variants: die Einträge sind Fassungen derselben Vorlage."""
    sources = [s.strip() for s in sources if s and s.strip()]
    if not 1 <= len(sources) <= settings.MAX_REELS_PER_REQUEST:
        raise ContentError(f"Zwischen 1 und {settings.MAX_REELS_PER_REQUEST} Vorlagen pro Auftrag")
    store = get_store()
    niche = store.get(NICHES, niche_id)
    if niche.get("status") != "Approved":
        raise ContentError("Diese Nische ist noch nicht freigegeben")
    model = store.get(MODELS, niche["modelId"])
    if not model.get("referenceImages"):
        raise ContentError("Dieses Model hat noch keine Referenzfotos. Lade zuerst welche hoch.")
    if not get_provider().configured():
        raise ContentError("Die Video-Erzeugung ist nicht eingerichtet (KIE_API_KEY fehlt)")
    for source in sources:
        try:
            video.check_url(source)
        except video.VideoError as exc:
            raise ContentError(f"{exc}: {source[:80]}")
    number = len(store.list(CONTENT, {"modelId": model["id"]})) + 1
    created = []
    for offset, source in enumerate(sources):
        record = store.create(CONTENT, {
            "title": f"Reel {number + offset}: {niche['name']}" + (f" ({label})" if label else ""), "modelId": model["id"], "nicheId": niche["id"],
            "type": "Reel", "status": "Working", "step": "frame", "error": "", "images": [], "prompt": "",
            "sourceUrl": source, "sourceVideo": [], "frame": [], "finalReel": [], "videoModel": video_model,
            "tasks": {"image": {"phase": "new"}, "video": {"phase": "new"},
                      "variant": offset % len(VARIANTS) if as_variants else None},
        })
        jobs.start("reel_image", {"contentId": record["id"]}, subject=record["id"])
        created.append(record)
    return created


def _fail(content_id, tasks, message):
    get_store().update(CONTENT, content_id, {"status": "Failed", "error": message, "tasks": tasks})
    return {"contentId": content_id, "error": message}


def _await(receipt, wait_seconds, save):
    """Einen angenommenen Auftrag abfragen. Liefert die Ergebnis-Adresse, None bei
    Zeitüberschreitung (Quittung bleibt) oder wirft MediaError bei echtem Fehlschlag."""
    deadline = time.monotonic() + wait_seconds
    while True:
        result = get_provider().check(receipt["taskId"])
        if result["state"] == "success":
            receipt.update(phase="done", url=result["url"])
            save()
            return result["url"]
        if result["state"] == "fail":
            receipt.clear()
            receipt.update(phase="failed", error=result.get("error") or "Fehlgeschlagen")
            save()
            raise MediaError(receipt["error"])
        if time.monotonic() > deadline:
            return None
        time.sleep(settings.POLL_SECONDS)


def _send(receipt, save, submit):
    """Quittung vor dem Senden schreiben; bei unklarer Antwort nichts wiederholen."""
    receipt.clear()
    receipt["phase"] = "submitting"
    save()
    try:
        task_id = submit()
    except SubmissionUncertain:
        return False
    except MediaError:
        receipt["phase"] = "new"  # sicher abgelehnt: ein neuer Versuch ist gefahrlos
        save()
        raise
    receipt.update(phase="submitted", taskId=task_id)
    save()
    return True


# --- Schritt 1 und 2: Vorlage vorbereiten, Bild erzeugen ---------------------
def _prepare(content, tasks):
    """Vorlage laden und daraus zwei Dateien machen: das erste Bild und ein
    umgerechnetes Video mit Ton (zum Aufbewahren, für Kling und für den Ton)."""
    provider = get_provider()
    with video.workdir() as folder:
        raw = video.download(content["sourceUrl"], folder)
        seconds = video.duration(raw)
        trim = None
        if seconds > settings.MAX_SOURCE_SECONDS:
            if content.get("videoModel") == "kling-2.6":
                raise video.VideoError(
                    f"Die Vorlage ist {seconds:.0f} Sekunden lang. Kling 2.6 nimmt höchstens "
                    f"{settings.MAX_SOURCE_SECONDS} Sekunden. Kürze sie oder nimm Kling 3.0."
                )
            trim = settings.MAX_SOURCE_SECONDS
        frame_url = provider.host_file(video.first_frame(raw, folder).read_bytes(), "frame.jpg")
        kept_url = provider.host_file(video.normalize(raw, folder, audio=True, trim=trim).read_bytes(), "vorlage.mp4")
    return get_store().update(CONTENT, content["id"], {"frame": [frame_url], "sourceVideo": [kept_url], "tasks": tasks, "step": "image"})


def _image_prompt(niche, model, variant=None):
    outfits = prompts.varied_outfits(niche.get("outfits"), niche.get("nsfwLevel"))
    backgrounds = [b for b in (niche.get("backgrounds") or []) if b]
    text = prompts.build_motion_image_prompt(outfit=random.choice(outfits), background=random.choice(backgrounds) if backgrounds else None)
    if variant is not None:
        text += VARIANT_RULES.format(variation=VARIANTS[variant])
    text += prompts.body_clause(model.get("bodyType"))
    text += prompts.market_cue(prompts.effective_market(niche.get("market"), model.get("language")), random.randint(0, 999))
    if niche.get("dressCode") == "authentic":
        text += " Authentic, realistic real-life uniform with accurate details." + prompts.name_tag_clause(model["name"])
    if niche.get("alwaysInclude"):
        text += f" MANDATORY: {niche['alwaysInclude']}"
    return text


@jobs.handler("reel_image", resume=True)
def run_image(payload):
    store = get_store()
    content = store.get(CONTENT, payload["contentId"])
    tasks = content.get("tasks") or {}
    receipt = tasks.setdefault("image", {"phase": "new"})

    def save(**fields):
        store.update(CONTENT, content["id"], {"tasks": tasks, **fields})

    try:
        if not content.get("frame"):
            content = _prepare(content, tasks)
        if receipt.get("phase") == "submitting":
            return _fail(content["id"], tasks, f"{UNCERTAIN}. »Erneut versuchen« sendet das Bild neu.")
        if not receipt.get("taskId") and not receipt.get("url"):
            niche = store.get(NICHES, content["nicheId"])
            model = store.get(MODELS, content["modelId"])
            prompt = _image_prompt(niche, model, tasks.get("variant"))
            # Reihenfolge der Vorlagen: zuerst das Bild aus dem Video (nur Pose), dann ihr Gesicht.
            references = list(content["frame"]) + list(model.get("referenceImages") or [])[:4]
            store.update(CONTENT, content["id"], {"prompt": prompt, "step": "image"})
            if not _send(receipt, save, lambda: get_provider().submit_image(prompt, references, aspect_ratio="9:16", resolution="2K")):
                return _fail(content["id"], tasks, f"{UNCERTAIN}. »Erneut versuchen« sendet das Bild neu.")
        url = receipt.get("url") or _await(receipt, settings.IMAGE_WAIT_SECONDS, save)
    except (video.VideoError, MediaError) as exc:
        return _fail(content["id"], tasks, str(exc))
    if not url:
        return _fail(content["id"], tasks, "Das Bild braucht ungewöhnlich lange. »Erneut versuchen« fragt denselben Auftrag weiter ab, ohne neu zu bezahlen.")
    save(images=[url], status="Review", step="image", error="")
    return {"contentId": content["id"], "step": "image"}


# --- Schritt 3: Video --------------------------------------------------------
@jobs.handler("reel_video", resume=True)
def run_video(payload):
    store = get_store()
    content = store.get(CONTENT, payload["contentId"])
    if content.get("finalReel"):
        return {"contentId": content["id"], "step": "video"}
    tasks = content.get("tasks") or {}
    receipt = tasks.setdefault("video", {"phase": "new"})
    provider = get_provider()

    def save(**fields):
        store.update(CONTENT, content["id"], {"tasks": tasks, **fields})

    try:
        if receipt.get("phase") == "submitting":
            return _fail(content["id"], tasks, f"{UNCERTAIN}. »Erneut versuchen« sendet das Video neu.")
        if not receipt.get("taskId") and not receipt.get("url"):
            if not content.get("images") or not content.get("sourceVideo"):
                return _fail(content["id"], tasks, "Bild oder Vorlage fehlen")
            with video.workdir() as folder:
                # Beide Dateien frisch beim Anbieter ablegen: gespeicherte Links laufen ab.
                image_url = provider.host_file(video.fetch(content["images"][0], folder / "bild.png").read_bytes(), "bild.png")
                source = video.fetch(content["sourceVideo"][0], folder / "vorlage.mp4")
                motion_url = provider.host_file(video.normalize(source, folder, audio=False).read_bytes(), "bewegung.mp4")
            model_name = content.get("videoModel") or "kling-3.0"
            if not _send(receipt, save, lambda: provider.submit_video(VIDEO_PROMPT, image_url, motion_url, model_name)):
                return _fail(content["id"], tasks, f"{UNCERTAIN}. »Erneut versuchen« sendet das Video neu.")
        url = receipt.get("url") or _await(receipt, settings.VIDEO_WAIT_SECONDS, save)
        if not url:
            return _fail(content["id"], tasks, "Das Video braucht ungewöhnlich lange. »Erneut versuchen« fragt denselben Auftrag weiter ab, ohne neu zu bezahlen.")
        # Kling liefert ohne Ton: den Ton der Vorlage zurücklegen (ohne Ton bleibt es stumm).
        with video.workdir() as folder:
            silent = video.fetch(url, folder / "stumm.mp4")
            source = video.fetch(content["sourceVideo"][0], folder / "vorlage.mp4")
            final = video.mux_audio(silent, source, folder) or silent
            final_url = provider.host_file(final.read_bytes(), "reel.mp4")
    except (video.VideoError, MediaError) as exc:
        return _fail(content["id"], tasks, str(exc))
    save(finalReel=[final_url], status="Review", step="video", error="")
    return {"contentId": content["id"], "step": "video"}


# --- Entscheidungen ----------------------------------------------------------
def approve(content):
    """Bild freigeben startet das Video; Video freigeben schließt das Reel ab."""
    store = get_store()
    if content["step"] == "image":
        store.update(CONTENT, content["id"], {"status": "Working", "step": "video", "error": ""})
        jobs.start("reel_video", {"contentId": content["id"]}, subject=content["id"])
        return store.get(CONTENT, content["id"])
    if not content.get("finalReel"):
        raise ContentError("Ohne Video gibt es nichts freizugeben")
    return store.update(CONTENT, content["id"], {"status": "Approved"})


def retry(content, fresh_image=False):
    """Den aktuellen Schritt noch einmal versuchen. Offene Aufträge werden weiter
    abgefragt; nur ein unklarer oder gescheiterter Auftrag wird neu gesendet.
    fresh_image=True verwirft das Bild und erzeugt (bezahlt) ein neues."""
    store = get_store()
    if jobs.active(subject=content["id"]):
        raise ContentError("Dafür läuft bereits ein Auftrag")
    tasks = content.get("tasks") or {}
    step = "video" if content["step"] == "video" else "image"
    if fresh_image:
        if content["step"] != "image":
            raise ContentError("Ein neues Bild geht nur vor dem Video")
        tasks["image"] = {"phase": "new"}
    receipt = tasks.setdefault(step, {"phase": "new"})
    if not receipt.get("taskId") and not receipt.get("url"):
        receipt.clear()
        receipt["phase"] = "new"
    fields = {"status": "Working", "error": "", "tasks": tasks}
    if fresh_image:
        fields["images"] = []
    store.update(CONTENT, content["id"], fields)
    jobs.start("reel_video" if step == "video" else "reel_image", {"contentId": content["id"]}, subject=content["id"])
    return store.get(CONTENT, content["id"])
