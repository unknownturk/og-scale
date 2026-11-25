from app.llm import LLMError
from .conftest import GOOD


def niches_of(client, model):
    return client.get(f"/models/{model['id']}/niches").json()


def test_requires_key(client):
    assert client.get("/models", headers={"X-API-Key": "wrong"}).status_code == 401


def test_generate_saves_validated_proposals(client, ai, model):
    ai["answer"] = {"niches": [GOOD, {**GOOD, "name": "Beach"}]}
    job = client.post(f"/models/{model['id']}/niches/generate", json={"count": 2}).json()
    assert job["status"] == "succeeded" and job["result"]["count"] == 2
    saved = niches_of(client, model)
    assert [n["status"] for n in saved] == ["Proposed", "Proposed"]
    assert saved[0]["styleVibe"] == "cool studio light"
    assert saved[0]["scenarios"][0]["camera"] == "low angle"  # Zusatzfelder bleiben erhalten


def test_empty_ai_answer_fails_and_saves_nothing(client, ai, model):
    ai["answer"] = {"niches": []}
    job = client.post(f"/models/{model['id']}/niches/generate", json={"count": 3}).json()
    assert job["status"] == "failed" and "keine Nische" in job["error"]
    assert niches_of(client, model) == []


def test_one_broken_niche_saves_none(client, ai, model):
    ai["answer"] = {"niches": [GOOD, {"name": "Kaputt", "outfits": [], "backgrounds": ["x"]}]}
    job = client.post(f"/models/{model['id']}/niches/generate", json={"count": 2}).json()
    assert job["status"] == "failed" and "unvollständig" in job["error"]
    assert niches_of(client, model) == []


def test_bare_object_without_niches_key_is_accepted(client, ai, model):
    ai["answer"] = GOOD
    job = client.post(f"/models/{model['id']}/niches/from-brief", json={"brief": "Fitnessstudio, enge Sets"}).json()
    assert job["status"] == "succeeded"
    assert niches_of(client, model)[0]["source"] == "Brief"


def test_ai_error_is_reported(client, ai, model):
    ai["answer"] = LLMError("Die KI hat nicht rechtzeitig geantwortet")
    job = client.post(f"/models/{model['id']}/niches/generate", json={"count": 1}).json()
    assert job["status"] == "failed" and "rechtzeitig" in job["error"]


def test_count_is_capped(client, ai, model):
    assert client.post(f"/models/{model['id']}/niches/generate", json={"count": 50}).status_code == 422


def test_improve_is_only_a_proposal(client, ai, model):
    ai["answer"] = GOOD
    client.post(f"/models/{model['id']}/niches/generate", json={"count": 1})
    niche = niches_of(client, model)[0]
    ai["answer"] = {"niches": [{**GOOD, "name": "Anders", "outfits": ["a new outfit"]}]}
    job = client.post(f"/niches/{niche['id']}/improve", json={"hint": "mehr Strand"}).json()
    assert job["result"]["proposal"]["outfits"] == ["a new outfit"]
    assert job["result"]["proposal"]["name"] == "Gym Girl"  # Name bleibt
    assert client.get(f"/niches/{niche['id']}").json()["outfits"] == GOOD["outfits"]  # nichts überschrieben


def test_failed_improve_leaves_niche_untouched(client, ai, model):
    ai["answer"] = GOOD
    client.post(f"/models/{model['id']}/niches/generate", json={"count": 1})
    niche = niches_of(client, model)[0]
    ai["answer"] = {"niches": [{}]}
    job = client.post(f"/niches/{niche['id']}/improve", json={}).json()
    assert job["status"] == "failed"
    assert client.get(f"/niches/{niche['id']}").json()["outfits"] == GOOD["outfits"]


def test_status_and_edit(client, ai, model):
    ai["answer"] = GOOD
    client.post(f"/models/{model['id']}/niches/generate", json={"count": 1})
    niche = niches_of(client, model)[0]
    assert client.post(f"/niches/{niche['id']}/status", json={"status": "Approved"}).json()["status"] == "Approved"
    assert client.post(f"/niches/{niche['id']}/status", json={"status": "Egal"}).status_code == 422
    assert client.patch(f"/niches/{niche['id']}", json={"outfits": []}).status_code == 422  # nie leer
    assert client.patch(f"/niches/{niche['id']}", json={"nsfwLevel": "wild"}).status_code == 422
    assert client.patch(f"/niches/{niche['id']}", json={"hooks": ["Neu"]}).json()["hooks"] == ["Neu"]
    assert client.get("/models").json()[0]["nicheCounts"]["Approved"] == 1


def test_model_with_niches_cannot_be_deleted(client, ai, model):
    ai["answer"] = GOOD
    client.post(f"/models/{model['id']}/niches/generate", json={"count": 1})
    assert client.delete(f"/models/{model['id']}").status_code == 409
    client.delete(f"/niches/{niches_of(client, model)[0]['id']}")
    assert client.delete(f"/models/{model['id']}").status_code == 204


def test_missing_records_are_404(client):
    assert client.get("/niches/recNope").status_code == 404
    assert client.post("/models/recNope/niches/generate", json={"count": 1}).status_code == 404
