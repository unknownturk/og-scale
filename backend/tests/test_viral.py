from datetime import datetime, timedelta, timezone

import pytest

from app import settings
from app.store import SOURCES, VIRAL, get_store
from app.viral import scrapers, service

from .test_content import niche, provider  # noqa: F401
from .test_reels import clip, web  # noqa: F401


def reel(owner, n, views, hours=10, video="http://x/v.mp4"):
    posted = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    return {"url": f"https://www.instagram.com/reel/{owner}{n}/", "owner": owner, "videoUrl": video, "thumbnail": "http://x/t.jpg",
            "caption": "c", "likes": views // 20, "comments": 3, "views": views, "postedAt": posted}


@pytest.fixture
def scraped(monkeypatch):
    box = {"reels": [], "errors": []}
    monkeypatch.setattr(scrapers, "provider_name", lambda: "test")
    monkeypatch.setattr(scrapers, "scrape", lambda handles: (list(box["reels"]), list(box["errors"])))
    return box


def test_sources_are_cleaned_and_deduplicated(client):
    r = client.post("/viral/sources", json={"handles": ["@Lena.Fit", "https://www.instagram.com/mia_x/", "lena.fit", "  ", "böse name!"]}).json()
    assert [s["handle"] for s in r["created"]] == ["lena.fit", "mia_x"]
    assert r["skipped"] == ["lena.fit", "böse name!"]
    sid = r["created"][0]["id"]
    assert client.patch(f"/viral/sources/{sid}", json={"state": "Disabled"}).json()["state"] == "Disabled"
    assert client.delete(f"/viral/sources/{sid}").status_code == 204


def test_scrape_scores_and_dedupes(client, scraped):
    client.post("/viral/sources", json={"handles": ["a", "b"], "market": "US", "category": "gym"})
    scraped["reels"] = [reel("a", 1, 1000), reel("a", 2, 1000), reel("a", 3, 90000), reel("b", 1, 500, hours=300)]
    job = client.post("/viral/scrape").json()
    assert job["status"] == "succeeded" and job["result"]["created"] == 4 and job["result"]["sourcesWithReels"] == 2
    rows = client.get("/viral/reels").json()
    assert rows[0]["reelUrl"].endswith("a3/") and rows[0]["outperform"] == 90.0 and rows[0]["market"] == "US"
    assert rows[0]["potential"] > rows[-1]["potential"]
    assert client.get("/viral/reels?sort=views&owner=b").json()[0]["views"] == 500
    # zweiter Lauf: nichts doppelt, Zahlen und Video-Link werden aufgefrischt
    scraped["reels"] = [reel("a", 3, 120000, video="http://x/neu.mp4")]
    assert client.post("/viral/scrape").json()["result"]["created"] == 0
    top = client.get("/viral/reels?sort=views").json()[0]
    assert top["views"] == 120000 and top["videoUrl"] == "http://x/neu.mp4"
    assert len(client.get("/viral/reels").json()) == 4
    assert client.get("/viral/status").json()["lastScrape"]


def test_empty_scrape_is_not_a_silent_success(client, scraped):
    client.post("/viral/sources", json={"handles": ["a"]})
    result = client.post("/viral/scrape").json()["result"]
    assert result["created"] == 0 and "leer" in result["errors"][0]
    scraped["errors"] = ["@a: HikerAPI 401"]
    assert client.post("/viral/scrape").json()["result"]["errors"] == ["@a: HikerAPI 401"]
    for s in get_store().list(SOURCES):
        get_store().delete(SOURCES, s["id"])
    assert "keine aktive Quelle" in client.post("/viral/scrape").json()["error"]


def test_old_unused_reels_are_pruned_but_imported_stay(client, scraped):
    store = get_store()
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    store.create(VIRAL, {"reelUrl": "u1", "owner": "a", "status": "New", "scrapedAt": old, "views": 1})
    store.create(VIRAL, {"reelUrl": "u2", "owner": "a", "status": "Imported", "scrapedAt": old, "views": 1})
    assert service.prune() == 1
    assert [r["reelUrl"] for r in store.list(VIRAL)] == ["u2"]


def test_dismiss_and_restore(client, scraped):
    client.post("/viral/sources", json={"handles": ["a"]})
    scraped["reels"] = [reel("a", 1, 1000)]
    client.post("/viral/scrape")
    vid = client.get("/viral/reels").json()[0]["id"]
    client.post(f"/viral/reels/{vid}/status", json={"status": "Dismissed"})
    assert client.get("/viral/reels").json() == []
    assert len(client.get("/viral/reels?dismissed=true").json()) == 1


def test_import_creates_distinct_variants(client, niche, web, scraped):  # noqa: F811
    client.post("/viral/sources", json={"handles": ["a"]})
    scraped["reels"] = [reel("a", 1, 1000, video=clip("viral.mp4"))]
    client.post("/viral/scrape")
    vid = client.get("/viral/reels").json()[0]["id"]
    r = client.post("/viral/import", json={"viralIds": [vid], "nicheId": niche["id"], "variants": 3})
    assert r.status_code == 202 and r.json()["count"] == 3
    prompts_sent = [t["prompt"] for t in web.tasks.values()]
    assert sum("neutral natural light" in p for p in prompts_sent) == 1
    assert sum("warmer natural light" in p for p in prompts_sent) == 1
    assert sum("cooler natural light" in p for p in prompts_sent) == 1
    row = client.get("/viral/reels").json()[0]
    assert row["status"] == "Imported" and len(row["importedContent"]) == 3
    content = client.get(f"/content/{r.json()['contentIds'][0]}").json()
    assert content["status"] == "Review" and "(@a)" in content["title"]
    assert client.post(f"/viral/reels/{vid}/status", json={"status": "Dismissed"}).status_code == 409


def test_import_limits(client, niche, scraped, monkeypatch):  # noqa: F811
    monkeypatch.setattr(settings, "MAX_VIRAL_IMPORT", 4)
    store = get_store()
    ids = [store.create(VIRAL, {"reelUrl": f"u{i}", "owner": "a", "videoUrl": "http://x/v.mp4", "status": "New"})["id"] for i in range(2)]
    r = client.post("/viral/import", json={"viralIds": ids, "nicheId": niche["id"], "variants": 3})
    assert r.status_code == 409 and "6 Reels" in r.json()["detail"]
    nolink = store.create(VIRAL, {"reelUrl": "u9", "owner": "b", "videoUrl": "", "status": "New"})["id"]
    assert "Ohne Video-Link" in client.post("/viral/import", json={"viralIds": [nolink], "nicheId": niche["id"]}).json()["detail"]


def test_auto_scrape_only_when_due(client, scraped, monkeypatch):
    assert service.auto_scrape_if_due() is False  # keine Quelle
    client.post("/viral/sources", json={"handles": ["a"]})
    scraped["reels"] = [reel("a", 1, 10)]
    assert service.auto_scrape_if_due() is True
    assert service.auto_scrape_if_due() is False  # gerade erst gelesen
    monkeypatch.setattr(settings, "VIRAL_AUTO_HOURS", 0)
    assert service.auto_scrape_if_due() is False


def test_hikerapi_parsing(monkeypatch):
    monkeypatch.setattr(settings, "HIKERAPI_TOKEN", "t")
    monkeypatch.setattr(settings, "MEDIA_PROVIDER", "kie")
    payload = {"response": {"items": [
        {"media": {"code": "ABC", "video_versions": [{"url": "http://v/1.mp4"}], "caption": {"text": "hi"}, "like_count": 5,
                   "play_count": 900, "taken_at": 1700000000, "user": {"username": "Lena"}, "thumbnail_url": "http://t/1.jpg"}},
        {"media": {"code": "NOVIDEO"}},
    ]}}
    monkeypatch.setattr(scrapers, "_hiker_get", lambda path, params: payload)
    reels, errors = scrapers.scrape(["lena"])
    assert errors == [] and len(reels) == 1
    assert reels[0]["url"] == "https://www.instagram.com/reel/ABC/" and reels[0]["owner"] == "lena" and reels[0]["views"] == 900
    monkeypatch.setattr(scrapers, "_hiker_get", lambda path, params: (_ for _ in ()).throw(scrapers.ScrapeError("401")))
    assert scrapers.scrape(["lena"]) == ([], ["@lena: 401"])
