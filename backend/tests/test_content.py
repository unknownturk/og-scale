import pytest

from app import jobs, settings
from app.content import images
from app.media import MediaError, SubmissionUncertain, set_provider
from app.media.fake import FakeProvider
from app.store import CONTENT, MODELS, NICHES, get_store

from .conftest import GOOD


@pytest.fixture
def provider(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "FILES_DIR", tmp_path)
    monkeypatch.setattr(settings, "POLL_SECONDS", 0)
    monkeypatch.setattr(settings, "MEDIA_PROVIDER", "fake")
    fake = FakeProvider()
    set_provider(fake)
    return fake


@pytest.fixture
def niche(client, model, provider):
    store = get_store()
    store.update(MODELS, model["id"], {"referenceImages": ["http://x/ref1.jpg", "http://x/ref2.jpg"], "bodyType": "athletic"})
    spec = {k: v for k, v in GOOD.items() if k in ("name", "outfits", "backgrounds", "scenarios", "hooks", "themes")}
    return store.create(NICHES, {**spec, "modelId": model["id"], "status": "Approved", "market": "DE", "nsfwLevel": "sfw", "dressCode": ""})


def make(client, niche, **body):
    return client.post(f"/niches/{niche['id']}/content/images", json={"kind": "carousel", "count": 3, **body})


def test_carousel_is_one_record_with_all_images(client, niche, provider):
    created = make(client, niche).json()
    assert len(created) == 1
    content = client.get(f"/content/{created[0]['id']}").json()
    assert content["status"] == "Review" and content["imageCount"] == 3 and content["type"] == "Carousel"
    assert "tasks" not in content  # interne Quittungen bleiben intern
    prompts_sent = [t["prompt"] for t in provider.tasks.values()]
    assert all("IDENTITY" in p and "athletic" in p for p in prompts_sent)
    refs = [t["references"] for t in provider.tasks.values()]
    assert refs[0] == ["http://x/ref1.jpg", "http://x/ref2.jpg"]
    assert len(refs[1]) == 3  # Folgebilder bekommen das erste Bild als Vorlage


def test_photos_are_separate_records(client, niche):
    created = make(client, niche, kind="photos", count=2).json()
    assert [c["type"] for c in created] == ["Photo", "Photo"]
    assert all(client.get(f"/content/{c['id']}").json()["imageCount"] == 1 for c in created)


def test_guards(client, niche, model):
    assert make(client, niche, count=50).status_code == 422
    get_store().update(NICHES, niche["id"], {"status": "Proposed"})
    assert "nicht freigegeben" in make(client, niche).json()["detail"]
    get_store().update(NICHES, niche["id"], {"status": "Approved"})
    get_store().update(MODELS, model["id"], {"referenceImages": []})
    assert "Referenzfotos" in make(client, niche).json()["detail"]


def test_failed_image_keeps_the_finished_ones(client, niche, provider):
    provider.fail_next = ["", "GPU exploded"]
    content = client.get(f"/content/{make(client, niche).json()[0]['id']}").json()
    assert content["status"] == "Review" and content["imageCount"] == 2
    assert "1 Bild(er) fehlgeschlagen" in content["error"]


def test_moderation_reject_retries_with_milder_prompt(client, niche, provider):
    provider.fail_next = ["Your prompt failed the review"]
    content = client.get(f"/content/{make(client, niche, count=1).json()[0]['id']}").json()
    assert content["status"] == "Review" and content["imageCount"] == 1
    assert len(provider.tasks) == 2


def test_uncertain_submit_is_not_repeated_until_retry(client, niche, provider, monkeypatch):
    calls = {"n": 0}
    real = provider.submit_image

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise SubmissionUncertain("lost")
        return real(*a, **k)

    monkeypatch.setattr(provider, "submit_image", flaky)
    cid = make(client, niche, kind="photos", count=1).json()[0]["id"]
    content = client.get(f"/content/{cid}").json()
    assert content["status"] == "Failed" and "unklar" in content["error"] and calls["n"] == 1
    assert client.post(f"/content/{cid}/retry").status_code == 202
    assert client.get(f"/content/{cid}").json()["status"] == "Review" and calls["n"] == 2


def test_slow_task_is_polled_again_not_resubmitted(client, niche, provider, monkeypatch):
    slow = {"on": True}
    real_check = provider.check
    monkeypatch.setattr(provider, "check", lambda t: {"state": "waiting"} if slow["on"] else real_check(t))
    monkeypatch.setattr(settings, "IMAGE_WAIT_SECONDS", -1)
    cid = make(client, niche, kind="photos", count=1).json()[0]["id"]
    assert client.get(f"/content/{cid}").json()["status"] == "Failed"
    assert len(provider.tasks) == 1
    slow["on"] = False
    monkeypatch.setattr(settings, "IMAGE_WAIT_SECONDS", 60)
    client.post(f"/content/{cid}/retry")
    assert client.get(f"/content/{cid}").json()["status"] == "Review"
    assert len(provider.tasks) == 1  # derselbe Auftrag, nicht neu bezahlt


def test_resume_after_restart_uses_saved_task(client, niche, provider):
    store = get_store()
    task_id = provider.submit_image("p", [])
    record = store.create(CONTENT, {"title": "t", "modelId": niche["modelId"], "nicheId": niche["id"], "type": "Photo",
                                    "status": "Working", "step": "images", "mode": "niche", "images": [],
                                    "tasks": {"slots": [{"phase": "submitted", "taskId": task_id}]}})
    images.run({"contentId": record["id"]})
    assert store.get(CONTENT, record["id"])["status"] == "Review" and len(provider.tasks) == 1


def test_decisions(client, niche):
    cid = make(client, niche, count=1).json()[0]["id"]
    assert client.post(f"/content/{cid}/decision", json={"decision": "reopen"}).status_code == 409
    assert client.post(f"/content/{cid}/decision", json={"decision": "approve"}).json()["status"] == "Approved"
    assert client.post(f"/content/{cid}/decision", json={"decision": "approve"}).status_code == 409
    assert client.post(f"/content/{cid}/decision", json={"decision": "reopen"}).json()["status"] == "Review"
    assert client.delete(f"/niches/{niche['id']}").status_code == 409  # Nische mit Content bleibt
    assert client.delete(f"/content/{cid}").status_code == 204


def test_reference_upload_and_media(client, model, provider, monkeypatch):
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
    r = client.post(f"/models/{model['id']}/references", files=[("files", ("a.png", png, "image/png"))])
    assert r.status_code == 200 and len(r.json()["referenceImages"]) == 1
    assert client.post(f"/models/{model['id']}/references", files=[("files", ("a.gif", png, "image/gif"))]).status_code == 415
    too_many = [("files", (f"{i}.png", png, "image/png")) for i in range(6)]
    assert client.post(f"/models/{model['id']}/references", files=too_many).status_code == 409
    name = r.json()["referenceImages"][0].rsplit("/", 1)[-1]
    assert client.get(f"/files/{name}").content == png

    class Up:
        status_code, content, headers = 200, png, {"content-type": "image/png"}

    monkeypatch.setattr("app.api.content.requests.get", lambda url, timeout: Up())
    assert client.get(f"/media/models/{model['id']}/referenceImages/0").content == png
    assert client.get(f"/media/models/{model['id']}/referenceImages/5").status_code == 404
    assert client.get(f"/media/models/{model['id']}/notes/0").status_code == 404
    assert client.delete(f"/models/{model['id']}/references/0").json()["referenceImages"] == []


def test_kie_submit_never_retries_ambiguous_errors(monkeypatch):
    import requests
    from app.media import kie

    monkeypatch.setattr(settings, "KIE_API_KEY", "k")
    monkeypatch.setattr(kie.time, "sleep", lambda s: None)
    calls = []

    class R:
        def __init__(self, status, body):
            self.status_code, self._b = status, body

        def json(self):
            return self._b

    def post(url, **k):
        calls.append(url)
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(kie.requests, "post", post)
    p = kie.KieProvider()
    queue = [R(429, {}), R(200, {"code": 200, "data": {"taskId": "T1"}})]
    assert p.submit_image("x", []) == "T1" and len(calls) == 2
    for bad in (requests.Timeout(), R(502, {}), R(200, {"code": 200})):
        calls.clear()
        queue = [bad, R(200, {"data": {"taskId": "NIE"}})]
        with pytest.raises(SubmissionUncertain):
            p.submit_image("x", [])
        assert len(calls) == 1
    queue = [R(200, {"code": 422, "msg": "bad input"})]
    with pytest.raises(MediaError, match="bad input"):
        p.submit_image("x", [])
