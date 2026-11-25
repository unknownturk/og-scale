"""Routen für Viral Content."""

from typing import Literal, Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from .. import jobs, settings
from ..auth import require_key
from ..content import video
from ..content.images import ContentError
from ..store import SOURCES, VIRAL, NotFound, get_store
from ..viral import scrapers, service

router = APIRouter(dependencies=[Depends(require_key)])
Market = Literal["DE", "US"]


def _get(table, record_id):
    try:
        return get_store().get(table, record_id)
    except NotFound:
        raise HTTPException(404, "Nicht gefunden")


class SourcesIn(BaseModel):
    handles: list[str] = Field(min_length=1, max_length=200)
    market: Market = "DE"
    category: str = Field(default="", max_length=60)


class SourcePatch(BaseModel):
    market: Optional[Market] = None
    category: Optional[str] = Field(default=None, max_length=60)
    state: Optional[Literal["Active", "Disabled"]] = None


@router.get("/viral/sources")
def list_sources():
    return sorted(get_store().list(SOURCES), key=lambda s: s["handle"])


@router.post("/viral/sources", status_code=201)
def add_sources(body: SourcesIn):
    return service.add_sources(body.handles, body.market, body.category)


@router.patch("/viral/sources/{source_id}")
def update_source(source_id: str, body: SourcePatch):
    _get(SOURCES, source_id)
    return get_store().update(SOURCES, source_id, body.model_dump(exclude_none=True))


@router.delete("/viral/sources/{source_id}", status_code=204)
def delete_source(source_id: str):
    _get(SOURCES, source_id)
    get_store().delete(SOURCES, source_id)


@router.get("/viral/status")
def status():
    running = jobs.active(subject=service.SCRAPE_SUBJECT)
    return {"provider": scrapers.provider_name(), "lastScrape": service.last_scrape(),
            "running": bool(running), "jobId": running[0]["id"] if running else None,
            "autoHours": settings.VIRAL_AUTO_HOURS}


@router.post("/viral/scrape", status_code=202)
def scrape():
    if not scrapers.provider_name():
        raise HTTPException(503, "Zum Lesen fremder Reels fehlt HIKERAPI_TOKEN oder APIFY_TOKEN")
    try:
        return service.start_scrape()
    except ContentError as exc:
        raise HTTPException(409, str(exc))


@router.get("/viral/reels")
def list_reels(market: str = "", owner: str = "", sort: str = "potential", dismissed: bool = False):
    return service.list_reels(market, owner, sort, dismissed)


class StatusIn(BaseModel):
    status: Literal["New", "Dismissed"]


@router.post("/viral/reels/{viral_id}/status")
def set_status(viral_id: str, body: StatusIn):
    row = _get(VIRAL, viral_id)
    if row.get("status") == "Imported":
        raise HTTPException(409, "Dieses Reel ist schon verwendet")
    return get_store().update(VIRAL, viral_id, {"status": body.status})


class ImportIn(BaseModel):
    viralIds: list[str] = Field(min_length=1, max_length=settings.MAX_VIRAL_IMPORT)
    nicheId: str
    variants: int = Field(default=1, ge=1, le=3)
    videoModel: Literal["kling-3.0", "kling-2.6"] = "kling-3.0"


@router.post("/viral/import", status_code=202)
def import_reels(body: ImportIn):
    try:
        return service.import_reels(body.viralIds, body.nicheId, body.variants, body.videoModel)
    except NotFound:
        raise HTTPException(404, "Nicht gefunden")
    except ContentError as exc:
        raise HTTPException(409, str(exc))


@router.get("/viral/reels/{viral_id}/{kind}")
def reel_media(viral_id: str, kind: Literal["thumbnail", "video"]):
    """Vorschaubild oder Video eines fremden Reels durchreichen (Instagram
    liefert sie dem Browser nicht direkt aus)."""
    url = _get(VIRAL, viral_id).get("thumbnail" if kind == "thumbnail" else "videoUrl")
    if not url:
        raise HTTPException(404, "Nicht vorhanden")
    try:
        video.check_url(url)
        upstream = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
    except (video.VideoError, requests.RequestException):
        raise HTTPException(502, "Nicht mehr abrufbar")
    if upstream.status_code != 200:
        raise HTTPException(502, "Nicht mehr abrufbar")
    return Response(upstream.content, media_type=upstream.headers.get("content-type", "application/octet-stream"),
                    headers={"Cache-Control": "private, max-age=3600"})
