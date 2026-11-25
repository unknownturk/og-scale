"""Reels fremder Accounts lesen. Ein Format für alle Anbieter:
{url, owner, videoUrl, thumbnail, caption, likes, comments, views, postedAt}."""

import time
from datetime import datetime, timezone

import requests

from .. import settings


class ScrapeError(RuntimeError):
    pass


def provider_name():
    if settings.MEDIA_PROVIDER == "fake":
        return "fake"
    if settings.HIKERAPI_TOKEN:
        return "hikerapi"
    if settings.APIFY_TOKEN:
        return "apify"
    return None


# --- HikerAPI ---------------------------------------------------------------
_HIKER = "https://api.hikerapi.com"
_RETRY = {429, 500, 502, 503, 504}


def _hiker_get(path, params):
    delay, last = 1.5, None
    for attempt in range(3):
        try:
            resp = requests.get(f"{_HIKER}{path}", params=params, timeout=90,
                                headers={"x-access-key": settings.HIKERAPI_TOKEN, "accept": "application/json"})
        except requests.RequestException as exc:
            last = ScrapeError(f"HikerAPI nicht erreichbar ({exc.__class__.__name__})")
        else:
            if resp.status_code < 400:
                return resp.json()
            last = ScrapeError(f"HikerAPI {resp.status_code}: {(resp.text or '')[:160]}")
            if resp.status_code not in _RETRY:
                raise last
        if attempt < 2:
            time.sleep(delay)
            delay *= 2
    raise last


def _items(data):
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "medias", "clips"):
            if isinstance(data.get(key), list):
                return [x for x in data[key] if isinstance(x, dict)]
        if isinstance(data.get("response"), dict):
            return _items(data["response"])
    return []


def _hiker(handle):
    try:
        items = _items(_hiker_get("/v2/user/clips", {"username": handle, "amount": settings.VIRAL_RESULTS_LIMIT}))
    except ScrapeError:
        items = []
    if not items:  # zweiter Weg über die Nutzer-Id
        user = _hiker_get("/v2/user/by/username", {"username": handle})
        inner = user.get("user") if isinstance(user.get("user"), dict) else user
        uid = inner.get("pk") or inner.get("id")
        if not uid:
            raise ScrapeError("Account nicht gefunden")
        items = _items(_hiker_get("/v1/user/clips", {"user_id": uid, "amount": settings.VIRAL_RESULTS_LIMIT}))
    out = []
    for item in items:
        media = item.get("media") if isinstance(item.get("media"), dict) else item
        code = media.get("code") or media.get("shortcode")
        video = media.get("video_url") or ((media.get("video_versions") or [{}])[0] or {}).get("url")
        if not code or not video:
            continue
        caption = media.get("caption_text")
        if caption is None and isinstance(media.get("caption"), dict):
            caption = media["caption"].get("text")
        try:
            posted = datetime.fromtimestamp(int(media.get("taken_at")), timezone.utc).isoformat()
        except (TypeError, ValueError):
            posted = ""
        user = media.get("user") if isinstance(media.get("user"), dict) else {}
        out.append({
            "url": f"https://www.instagram.com/reel/{code}/", "owner": (user.get("username") or handle).lower(),
            "videoUrl": video, "thumbnail": media.get("thumbnail_url") or "", "caption": (caption or "")[:2000],
            "likes": int(media.get("like_count") or 0), "comments": int(media.get("comment_count") or 0),
            "views": int(media.get("play_count") or media.get("view_count") or 0), "postedAt": posted,
        })
    return out


# --- Apify ------------------------------------------------------------------
def _apify(handles, errors):
    url = f"https://api.apify.com/v2/acts/{settings.APIFY_REEL_ACTOR}/run-sync-get-dataset-items"
    out = []
    for start in range(0, len(handles), 10):
        chunk = handles[start:start + 10]
        payload = {"username": chunk, "resultsLimit": settings.VIRAL_RESULTS_LIMIT, "skipPinnedPosts": False}
        if settings.VIRAL_NEWER_THAN:
            payload["onlyPostsNewerThan"] = settings.VIRAL_NEWER_THAN
        items, last = None, None
        for attempt in range(2):
            try:
                resp = requests.post(url, json=payload, timeout=320, params={"timeout": 300},
                                     headers={"Authorization": f"Bearer {settings.APIFY_TOKEN}"})
                resp.raise_for_status()
                items = resp.json() or []
                break
            except (requests.RequestException, ValueError) as exc:
                last = exc
                if attempt == 0:
                    time.sleep(3)
        if items is None:
            errors.append(f"{', '.join('@' + h for h in chunk[:3])}{' …' if len(chunk) > 3 else ''}: {str(last)[:160]}")
            continue
        for item in items:
            if not item.get("url") or not item.get("videoUrl") or (item.get("type") and item["type"] != "Video"):
                continue
            views = item.get("videoPlayCount") if item.get("videoPlayCount") is not None else item.get("videoViewCount")
            out.append({
                "url": item["url"], "owner": (item.get("ownerUsername") or "").lower(), "videoUrl": item["videoUrl"],
                "thumbnail": item.get("displayUrl") or "", "caption": (item.get("caption") or "")[:2000],
                "likes": int(item.get("likesCount") or 0), "comments": int(item.get("commentsCount") or 0),
                "views": int(views or 0), "postedAt": item.get("timestamp") or "",
            })
    return out


# --- Platzhalter (nur zum Ausprobieren) -------------------------------------
def _fake(handle):
    import hashlib
    from datetime import timedelta

    from ..media import get_provider
    from ..media.fake import _png, _silent_clip

    out = []
    for i in range(4):
        seed = int(hashlib.sha256(f"{handle}{i}".encode()).hexdigest()[:8], 16)
        out.append({
            "url": f"https://www.instagram.com/reel/{handle}{i}/", "owner": handle.lower(),
            "videoUrl": get_provider().host_file(_silent_clip(f"{handle}{i}"), "reel.mp4"),
            "thumbnail": get_provider().host_file(_png(f"{handle}{i}", 270, 480), "thumb.png"),
            "caption": ["POV: du wolltest nur kurz tanken", "Wer kennt es 😅", "Teil 2?", "Mein Montag in 10 Sekunden"][i],
            "likes": seed % 9000, "comments": seed % 300, "views": 5000 + seed % 900000,
            "postedAt": (datetime.now(timezone.utc) - timedelta(hours=6 + (seed % 200))).isoformat(),
        })
    return out


def scrape(handles):
    """Liefert (reels, fehler). Ein gescheiterter Account stoppt die anderen nicht."""
    name = provider_name()
    if not name:
        raise ScrapeError("Zum Lesen fremder Reels fehlt HIKERAPI_TOKEN oder APIFY_TOKEN")
    errors, reels = [], []
    if name == "apify":
        return _apify(handles, errors), errors
    for handle in handles:
        try:
            reels += _hiker(handle) if name == "hikerapi" else _fake(handle)
        except ScrapeError as exc:
            errors.append(f"@{handle}: {exc}")
    return reels, errors
