"""Routen für Content, Referenzfotos und Dateien."""

from typing import Literal, Optional

import requests
from fastapi import APIRouter, Depends, File, Header, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field

from .. import jobs, settings
from ..auth import require_key
from ..content import images, reels
from ..media import MediaError, get_provider
from ..store import CONTENT, MODELS, NotFound, get_store
from ..store.schema import TABLES

router = APIRouter(dependencies=[Depends(require_key)])
public = APIRouter()  # ohne Anmeldung: nur die Platzhalter-Dateien des Testanbieters

_IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def _get(table, record_id):
    try:
        return get_store().get(table, record_id)
    except NotFound:
        raise HTTPException(404, "Nicht gefunden")


class ImagesIn(BaseModel):
    kind: Literal["carousel", "photos"]
    count: int = Field(ge=1, le=settings.MAX_IMAGES_PER_REQUEST)
    mode: Literal["niche", "lifestyle", "story_daily", "story_me", "story_cta"] = "niche"
    styleIntensity: int = Field(default=60, ge=0, le=100)


def _view(content):
    """Für die Oberfläche: Fortschritt statt interner Quittungen."""
    slots = (content.get("tasks") or {}).get("slots") or []
    out = {k: v for k, v in content.items() if k != "tasks"}
    out["imageCount"] = len(content.get("images") or [])
    out["hasFrame"] = bool(content.get("frame"))
    out["hasVideo"] = bool(content.get("finalReel"))
    out["hasSource"] = bool(content.get("sourceVideo"))
    out["slotCount"] = 1 if content.get("type") == "Reel" else len(slots)
    return out


# --- Content ----------------------------------------------------------------
@router.post("/niches/{niche_id}/content/images", status_code=202)
def create_images(niche_id: str, body: ImagesIn):
    try:
        created = images.create(niche_id, body.kind, body.count, body.mode, body.styleIntensity)
    except NotFound:
        raise HTTPException(404, "Nicht gefunden")
    except images.ContentError as exc:
        raise HTTPException(409, str(exc))
    return [_view(c) for c in created]


class ReelsIn(BaseModel):
    sources: list[str] = Field(min_length=1, max_length=settings.MAX_REELS_PER_REQUEST)
    videoModel: Literal["kling-3.0", "kling-2.6"] = "kling-3.0"


@router.post("/niches/{niche_id}/content/reels", status_code=202)
def create_reels(niche_id: str, body: ReelsIn):
    try:
        created = reels.create(niche_id, body.sources, body.videoModel)
    except NotFound:
        raise HTTPException(404, "Nicht gefunden")
    except images.ContentError as exc:
        raise HTTPException(409, str(exc))
    return [_view(c) for c in created]


@router.post("/uploads/video")
async def upload_video(file: UploadFile = File(...)):
    """Eine Vorlage als Datei hochladen. Antwort: Adresse, die als Quelle dient."""
    if not (file.content_type or "").startswith("video/"):
        raise HTTPException(415, "Das ist keine Videodatei")
    provider = get_provider()
    if not provider.configured():
        raise HTTPException(503, "Hochladen ist nicht eingerichtet (KIE_API_KEY fehlt)")
    data = await file.read(settings.MAX_SOURCE_BYTES + 1)
    if len(data) > settings.MAX_SOURCE_BYTES:
        raise HTTPException(413, "Das Video ist größer als 200 MB")
    try:
        return {"url": provider.host_file(data, "vorlage.mp4")}
    except MediaError as exc:
        raise HTTPException(502, str(exc))


@router.get("/content")
def list_content(modelId: str = "", nicheId: str = ""):
    where = {k: v for k, v in (("modelId", modelId), ("nicheId", nicheId)) if v}
    rows = get_store().list(CONTENT, where or None)
    return [_view(c) for c in reversed(rows)]


@router.get("/content/{content_id}")
def get_content(content_id: str):
    return _view(_get(CONTENT, content_id))


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject", "reopen"]


@router.post("/content/{content_id}/decision")
def decide(content_id: str, body: DecisionIn):
    content = _get(CONTENT, content_id)
    allowed = {"approve": ("Review",), "reject": ("Review", "Failed"), "reopen": ("Approved", "Rejected")}
    if content["status"] not in allowed[body.decision]:
        raise HTTPException(409, "Das geht im jetzigen Zustand nicht")
    if body.decision == "approve":
        if not content.get("images"):
            raise HTTPException(409, "Ohne Bild gibt es nichts freizugeben")
        if content["type"] == "Reel":
            try:
                return _view(reels.approve(content))
            except images.ContentError as exc:
                raise HTTPException(409, str(exc))
    status = {"approve": "Approved", "reject": "Rejected", "reopen": "Review"}[body.decision]
    return _view(get_store().update(CONTENT, content_id, {"status": status}))


class RetryIn(BaseModel):
    freshImage: bool = False


@router.post("/content/{content_id}/retry", status_code=202)
def retry(content_id: str, body: Optional[RetryIn] = None):
    content = _get(CONTENT, content_id)
    try:
        if content["type"] == "Reel":
            reels.retry(content, fresh_image=bool(body and body.freshImage))
        else:
            images.retry(content_id)
    except images.ContentError as exc:
        raise HTTPException(409, str(exc))
    return _view(_get(CONTENT, content_id))


@router.delete("/content/{content_id}", status_code=204)
def delete_content(content_id: str):
    _get(CONTENT, content_id)
    if jobs.active(subject=content_id):
        raise HTTPException(409, "Dafür läuft noch ein Auftrag")
    get_store().delete(CONTENT, content_id)


# --- Referenzfotos eines Models ---------------------------------------------
@router.post("/models/{model_id}/references")
async def add_references(model_id: str, files: list[UploadFile] = File(...)):
    model = _get(MODELS, model_id)
    current = list(model.get("referenceImages") or [])
    if len(current) + len(files) > settings.MAX_REFERENCE_IMAGES:
        raise HTTPException(409, f"Höchstens {settings.MAX_REFERENCE_IMAGES} Referenzfotos pro Model")
    provider = get_provider()
    if not provider.configured():
        raise HTTPException(503, "Hochladen ist nicht eingerichtet (KIE_API_KEY fehlt)")
    urls = []
    for upload in files:
        ext = _IMAGE_TYPES.get(upload.content_type or "")
        if not ext:
            raise HTTPException(415, "Nur JPG, PNG oder WebP")
        data = await upload.read(settings.MAX_UPLOAD_BYTES + 1)
        if len(data) > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(413, "Ein Foto ist größer als 12 MB")
        try:
            urls.append(provider.host_file(data, f"referenz.{ext}"))
        except MediaError as exc:
            raise HTTPException(502, str(exc))
    return get_store().update(MODELS, model_id, {"referenceImages": current + urls})


@router.delete("/models/{model_id}/references/{index}")
def remove_reference(model_id: str, index: int):
    model = _get(MODELS, model_id)
    current = list(model.get("referenceImages") or [])
    if not 0 <= index < len(current):
        raise HTTPException(404, "Nicht gefunden")
    del current[index]
    return get_store().update(MODELS, model_id, {"referenceImages": current})


# --- Dateien anzeigen -------------------------------------------------------
_MEDIA = {"models": (MODELS, ("referenceImages",)), "content": (CONTENT, ("images", "frame", "sourceVideo", "finalReel"))}
_PASS = ("content-type", "content-length", "content-range", "accept-ranges")


@router.get("/media/{kind}/{record_id}/{field}/{index}")
def media(kind: str, record_id: str, field: str, index: int, range: Optional[str] = Header(default=None)):
    """Liefert eine gespeicherte Datei aus. Die Adresse wird bei jedem Abruf frisch
    aus dem Datensatz gelesen, weil Airtable-Links nach wenigen Stunden ablaufen.
    Teilabrufe (Range) gehen durch — iPhones spielen Videos sonst nicht ab."""
    if kind not in _MEDIA or field not in _MEDIA[kind][1] or field not in TABLES[_MEDIA[kind][0]]:
        raise HTTPException(404, "Nicht gefunden")
    urls = _get(_MEDIA[kind][0], record_id).get(field) or []
    if not 0 <= index < len(urls):
        raise HTTPException(404, "Nicht gefunden")
    try:
        upstream = requests.get(urls[index], timeout=60, headers={"Range": range} if range else {})
    except requests.RequestException:
        raise HTTPException(502, "Die Datei ist gerade nicht abrufbar")
    if upstream.status_code not in (200, 206):
        raise HTTPException(502, "Die Datei ist gerade nicht abrufbar")
    headers = {k: v for k, v in upstream.headers.items() if k.lower() in _PASS and k.lower() != "content-type"}
    headers["Cache-Control"] = "private, max-age=300"
    return Response(upstream.content, status_code=upstream.status_code, headers=headers,
                    media_type=upstream.headers.get("content-type", "application/octet-stream"))


@public.get("/files/{name}")
def fake_file(name: str):
    if settings.MEDIA_PROVIDER != "fake" or "/" in name or ".." in name:
        raise HTTPException(404, "Nicht gefunden")
    path = settings.FILES_DIR / name
    if not path.is_file():
        raise HTTPException(404, "Nicht gefunden")
    from fastapi.responses import FileResponse

    return FileResponse(path)  # kann Teilabrufe (Range)
