import subprocess

import pytest

from app import settings
from app.content import video
from app.media import SubmissionUncertain
from app.store import CONTENT, get_store

from .test_content import niche, provider  # noqa: F401


class Local:
    """Liefert die Dateien des Platzhalter-Anbieters ohne echten Webserver aus."""

    def __init__(self, url):
        path = settings.FILES_DIR / url.rsplit("/", 1)[-1]
        self.status_code = 200 if path.is_file() else 404
        self.content = path.read_bytes() if path.is_file() else b""

    def iter_content(self, size):
        yield self.content

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def clip(name, seconds=2, audio=True):
    target = settings.FILES_DIR / name
    args = ["ffmpeg", "-y", "-f", "lavfi", "-i", f"testsrc=s=180x320:d={seconds}:r=10"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac"]
    subprocess.run(args + ["-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)], check=True, capture_output=True)
    return f"{settings.PUBLIC_URL}/files/{name}"


@pytest.fixture
def web(monkeypatch, provider, tmp_path):  # noqa: F811
    monkeypatch.setattr(settings, "WORK_DIR", tmp_path / "work")
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_URLS", True)
    monkeypatch.setattr(video.requests, "get", lambda url, **k: Local(url))
    return provider


def streams(url):
    path = settings.FILES_DIR / url.rsplit("/", 1)[-1]
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True)
    return sorted(out.stdout.split())


def start(client, niche, source, **body):  # noqa: F811
    r = client.post(f"/niches/{niche['id']}/content/reels", json={"sources": [source], **body})
    assert r.status_code == 202, r.text
    return r.json()[0]["id"]


def test_full_reel_flow(client, niche, web):  # noqa: F811
    cid = start(client, niche, clip("quelle.mp4"))
    content = client.get(f"/content/{cid}").json()
    assert (content["status"], content["step"]) == ("Review", "image")
    assert content["hasFrame"] and content["hasSource"] and content["imageCount"] == 1 and not content["hasVideo"]
    image_task = next(t for t in web.tasks.values() if t.get("kind") != "video")
    assert image_task["references"][0] == get_store().get(CONTENT, cid)["frame"][0]  # Pose zuerst
    assert image_task["references"][1:] == ["http://x/ref1.jpg", "http://x/ref2.jpg"]
    assert "ULTRA-STRICT CHARACTER RECONSTRUCTION" in image_task["prompt"]

    content = client.post(f"/content/{cid}/decision", json={"decision": "approve"}).json()
    content = client.get(f"/content/{cid}").json()
    assert (content["status"], content["step"]) == ("Review", "video") and content["hasVideo"]
    video_task = next(t for t in web.tasks.values() if t.get("kind") == "video")
    assert video_task["model"] == "kling-3.0" and streams(video_task["video"]) == ["video"]  # Kling bekommt es ohne Ton
    record = get_store().get(CONTENT, cid)
    assert streams(record["finalReel"][0]) == ["audio", "video"]  # Ton der Vorlage liegt wieder drauf
    assert client.post(f"/content/{cid}/decision", json={"decision": "approve"}).json()["status"] == "Approved"
    assert not list(settings.WORK_DIR.glob("*"))  # Arbeitsdateien aufgeräumt


def test_source_without_audio_stays_silent(client, niche, web):  # noqa: F811
    cid = start(client, niche, clip("stumm.mp4", audio=False))
    client.post(f"/content/{cid}/decision", json={"decision": "approve"})
    assert streams(get_store().get(CONTENT, cid)["finalReel"][0]) == ["video"]


def test_bad_sources(client, niche, web, monkeypatch):  # noqa: F811
    cid = start(client, niche, f"{settings.PUBLIC_URL}/files/gibtsnicht.mp4")
    content = client.get(f"/content/{cid}").json()
    assert content["status"] == "Failed" and "nicht abrufbar" in content["error"] and not web.tasks
    (settings.FILES_DIR / "text.mp4").write_text("kein video")
    cid = start(client, niche, f"{settings.PUBLIC_URL}/files/text.mp4")
    assert "wirklich ein Video" in client.get(f"/content/{cid}").json()["error"] and not web.tasks
    monkeypatch.setattr(settings, "MAX_SOURCE_SECONDS", 1)
    cid = start(client, niche, clip("lang.mp4", seconds=3), videoModel="kling-2.6")
    assert "Kling 2.6" in client.get(f"/content/{cid}").json()["error"] and not web.tasks
    cid = start(client, niche, f"{settings.PUBLIC_URL}/files/lang.mp4")  # Kling 3.0 kürzt
    assert client.get(f"/content/{cid}").json()["status"] == "Review"
    monkeypatch.setattr(settings, "ALLOW_PRIVATE_URLS", False)
    for bad in ("file:///etc/passwd", "http://127.0.0.1/x.mp4", "http://169.254.169.254/latest"):
        r = client.post(f"/niches/{niche['id']}/content/reels", json={"sources": [bad]})
        assert r.status_code == 409, bad


def test_uncertain_video_submit_waits_for_retry(client, niche, web, monkeypatch):  # noqa: F811
    cid = start(client, niche, clip("q2.mp4"))
    calls = {"n": 0}
    real = web.submit_video

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SubmissionUncertain("lost")
        return real(*a, **k)

    monkeypatch.setattr(web, "submit_video", flaky)
    client.post(f"/content/{cid}/decision", json={"decision": "approve"})
    content = client.get(f"/content/{cid}").json()
    assert content["status"] == "Failed" and "Unklar" in content["error"] and calls["n"] == 1
    client.post(f"/content/{cid}/retry")
    assert client.get(f"/content/{cid}").json()["hasVideo"] and calls["n"] == 2


def test_slow_video_is_polled_again_not_paid_twice(client, niche, web, monkeypatch):  # noqa: F811
    cid = start(client, niche, clip("q3.mp4"))
    slow = {"on": True}
    real = web.check
    monkeypatch.setattr(web, "check", lambda t: {"state": "waiting"} if slow["on"] and t.startswith("fakevid") else real(t))
    monkeypatch.setattr(settings, "VIDEO_WAIT_SECONDS", -1)
    client.post(f"/content/{cid}/decision", json={"decision": "approve"})
    assert "ohne neu zu bezahlen" in client.get(f"/content/{cid}").json()["error"]
    slow["on"] = False
    monkeypatch.setattr(settings, "VIDEO_WAIT_SECONDS", 60)
    client.post(f"/content/{cid}/retry")
    assert client.get(f"/content/{cid}").json()["hasVideo"]
    assert sum(1 for t in web.tasks.values() if t.get("kind") == "video") == 1


def test_fresh_image_and_failed_image(client, niche, web):  # noqa: F811
    web.fail_next = ["content policy"]
    cid = start(client, niche, clip("q4.mp4"))
    assert client.get(f"/content/{cid}").json()["status"] == "Failed"
    client.post(f"/content/{cid}/retry")
    assert client.get(f"/content/{cid}").json()["status"] == "Review"
    before = get_store().get(CONTENT, cid)["images"]
    client.post(f"/content/{cid}/retry", json={"freshImage": True})
    after = get_store().get(CONTENT, cid)
    assert after["status"] == "Review" and after["images"] != before
    client.post(f"/content/{cid}/decision", json={"decision": "approve"})
    assert client.post(f"/content/{cid}/retry", json={"freshImage": True}).status_code == 409  # nach dem Video nicht mehr
