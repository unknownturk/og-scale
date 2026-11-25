"""Viral Content: Quellen pflegen, Reels lesen und bewerten, in Motion-Reels verwandeln."""

import math
from datetime import datetime, timedelta, timezone

from .. import jobs, settings
from ..content import reels as reel_content
from ..content.images import ContentError
from ..store import SOURCES, VIRAL, get_store
from . import scrapers

SCRAPE_SUBJECT = "viral-scrape"


def _now():
    return datetime.now(timezone.utc)


def clean_handle(raw):
    handle = (raw or "").strip().rstrip("/").rsplit("/", 1)[-1].lstrip("@").lower()
    return handle if handle and all(c.isalnum() or c in "._" for c in handle) else ""


# --- Quellen ----------------------------------------------------------------
def add_sources(handles, market="DE", category=""):
    """Mehrere Accounts auf einmal; schon vorhandene und ungültige werden übersprungen."""
    store = get_store()
    existing = {s["handle"] for s in store.list(SOURCES)}
    created, skipped = [], []
    for raw in handles:
        handle = clean_handle(raw)
        if not handle or handle in existing:
            if (raw or "").strip():
                skipped.append(raw.strip())
            continue
        existing.add(handle)
        created.append(store.create(SOURCES, {"handle": handle, "market": market, "category": category.strip(),
                                              "state": "Active", "lastScraped": ""}))
    return {"created": created, "skipped": skipped}


# --- Bewertung --------------------------------------------------------------
def _age_hours(posted):
    try:
        then = datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return max(1.0, (_now() - then).total_seconds() / 3600)
    except ValueError:
        return 24.0


def _median(values):
    values = sorted(v for v in values if v)
    if not values:
        return 0
    mid = len(values) // 2
    return values[mid] if len(values) % 2 else (values[mid - 1] + values[mid]) / 2


def score(reels, baseline=None):
    """Potenzial 0–100 aus Tempo (Views pro Stunde), Ausreißer gegenüber dem
    üblichen Reel des Accounts, Frische und Likes pro View."""
    by_owner = {}
    for reel in reels:
        by_owner.setdefault(reel["owner"], []).append(reel["views"])
    for owner, values in (baseline or {}).items():
        by_owner.setdefault(owner, []).extend(values)
    medians = {owner: _median(values) for owner, values in by_owner.items()}
    for reel in reels:
        age = _age_hours(reel.get("postedAt"))
        velocity = reel["views"] / age
        outperform = reel["views"] / (medians.get(reel["owner"]) or 1)
        speed = min(100, math.log10(velocity + 1) * 25)
        outlier = min(100, outperform * 33)
        fresh = max(0.0, 1 - (age / 24) / 14) * 100
        engaged = min(100, reel["likes"] / max(reel["views"], 1) * 1000)
        reel["viralScore"] = round(velocity, 1)
        reel["outperform"] = round(outperform, 1)
        reel["potential"] = int(round(0.4 * speed + 0.3 * outlier + 0.2 * fresh + 0.1 * engaged))
    return reels


# --- Lesen ------------------------------------------------------------------
@jobs.handler("viral_scrape")
def run_scrape(payload=None):
    store = get_store()
    sources = [s for s in store.list(SOURCES) if s.get("state") != "Disabled"]
    if not sources:
        raise ContentError("Es gibt noch keine aktive Quelle")
    try:
        found, errors = scrapers.scrape([s["handle"] for s in sources])
    except scrapers.ScrapeError as exc:
        raise ContentError(str(exc))
    stored = store.list(VIRAL)
    baseline = {}
    for row in stored:
        baseline.setdefault(row["owner"], []).append(row.get("views") or 0)
    by_handle = {s["handle"]: s for s in sources}
    existing = {row["reelUrl"]: row for row in stored}
    now = _now().isoformat()
    created = 0
    for reel in score(found, baseline):
        numbers = {k: reel[k] for k in ("likes", "comments", "views", "viralScore", "outperform", "potential")}
        known = existing.get(reel["url"])
        if known:
            # Frischer Video-Link (alte laufen ab) und aktuelle Zahlen.
            store.update(VIRAL, known["id"], {**numbers, "videoUrl": reel["videoUrl"], "thumbnail": reel["thumbnail"], "scrapedAt": now})
            continue
        source = by_handle.get(reel["owner"], {})
        store.create(VIRAL, {
            **numbers, "reelUrl": reel["url"], "owner": reel["owner"], "videoUrl": reel["videoUrl"],
            "thumbnail": reel["thumbnail"], "caption": reel["caption"], "postedAt": reel["postedAt"],
            "scrapedAt": now, "market": source.get("market") or "DE", "category": source.get("category") or "",
            "status": "New", "importedContent": [],
        })
        created += 1
    owners = {reel["owner"] for reel in found}
    for source in sources:
        if source["handle"] in owners:
            store.update(SOURCES, source["id"], {"lastScraped": now})
    if not found and not errors:
        errors.append("Alle Quellen kamen leer zurück. Prüfe Zugang und Guthaben beim Anbieter.")
    return {"created": created, "found": len(found), "sources": len(sources),
            "sourcesWithReels": len(owners), "errors": errors, "removed": prune()}


def prune():
    """Alte, nie benutzte Reels entfernen: ihre Video-Links sind abgelaufen."""
    store = get_store()
    cutoff = (_now() - timedelta(days=settings.VIRAL_RETENTION_DAYS)).isoformat()
    removed = 0
    for row in store.list(VIRAL):
        if row.get("status") != "Imported" and (row.get("scrapedAt") or "") < cutoff:
            store.delete(VIRAL, row["id"])
            removed += 1
    return removed


def start_scrape():
    if jobs.active(subject=SCRAPE_SUBJECT):
        raise ContentError("Es wird gerade schon gelesen")
    return jobs.start("viral_scrape", {}, subject=SCRAPE_SUBJECT)


def last_scrape():
    stamps = [s.get("lastScraped") for s in get_store().list(SOURCES) if s.get("lastScraped")]
    return max(stamps) if stamps else ""


def auto_scrape_if_due():
    """Vom Hintergrund-Takt aufgerufen. Startet höchstens einen Lauf."""
    if settings.VIRAL_AUTO_HOURS <= 0 or not scrapers.provider_name():
        return False
    sources = [s for s in get_store().list(SOURCES) if s.get("state") != "Disabled"]
    if not sources or jobs.active(subject=SCRAPE_SUBJECT):
        return False
    last = last_scrape()
    if last and datetime.fromisoformat(last) > _now() - timedelta(hours=settings.VIRAL_AUTO_HOURS):
        return False
    jobs.start("viral_scrape", {}, subject=SCRAPE_SUBJECT)
    return True


# --- Auswählen und verwandeln ------------------------------------------------
_SORT = {
    "potential": lambda r: r.get("potential") or 0,
    "views": lambda r: r.get("views") or 0,
    "recent": lambda r: r.get("postedAt") or "",
    "outperform": lambda r: r.get("outperform") or 0,
}


def list_reels(market="", owner="", sort="potential", include_dismissed=False):
    rows = [r for r in get_store().list(VIRAL)
            if (include_dismissed or r.get("status") != "Dismissed")
            and (not market or r.get("market") == market) and (not owner or r.get("owner") == owner)]
    return sorted(rows, key=_SORT.get(sort, _SORT["potential"]), reverse=True)


def import_reels(viral_ids, niche_id, variants=1, video_model="kling-3.0"):
    """Ausgewählte Reels als Vorlagen starten. variants = wie viele eigenständige
    Fassungen pro Vorlage (für mehrere Accounts derselben Nische)."""
    viral_ids = list(dict.fromkeys(viral_ids))
    if not viral_ids:
        raise ContentError("Wähle mindestens ein Reel")
    if not 1 <= variants <= 3:
        raise ContentError("Eine bis drei Fassungen pro Vorlage")
    if len(viral_ids) * variants > settings.MAX_VIRAL_IMPORT:
        raise ContentError(f"Das wären {len(viral_ids) * variants} Reels. Höchstens {settings.MAX_VIRAL_IMPORT} pro Import.")
    store = get_store()
    rows = [store.get(VIRAL, vid) for vid in viral_ids]
    missing = [r["owner"] for r in rows if not r.get("videoUrl")]
    if missing:
        raise ContentError(f"Ohne Video-Link: @{', @'.join(missing)}. Lies die Quellen neu.")
    started = []
    for row in rows:
        created = reel_content.create(niche_id, [row["videoUrl"]] * variants, video_model,
                                      label=f"@{row['owner']}", as_variants=variants > 1)
        ids = [c["id"] for c in created]
        store.update(VIRAL, row["id"], {"status": "Imported", "importedContent": (row.get("importedContent") or []) + ids})
        started += ids
    return {"contentIds": started, "count": len(started)}
