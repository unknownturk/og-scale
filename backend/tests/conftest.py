import pytest
from fastapi.testclient import TestClient

from app import jobs, llm, settings
from app.store import MemoryStore, set_store


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "BACKEND_API_KEY", "test-key")
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "test-openrouter")
    monkeypatch.setattr(settings, "DEMO_SEED", False)
    set_store(MemoryStore())
    jobs.init("sqlite:///:memory:")
    # Aufträge laufen im Test sofort und im selben Thread.
    real_start = jobs.start
    monkeypatch.setattr(jobs, "start", lambda *a, **k: real_start(*a, **{**k, "run_inline": True}))
    from app.main import app

    c = TestClient(app)
    c.headers["X-API-Key"] = "test-key"
    return c


@pytest.fixture
def ai(monkeypatch):
    """Stellt ein, was die KI als Nächstes antwortet."""
    box = {"answer": None, "calls": 0}

    def fake(prompt, **kwargs):
        box["calls"] += 1
        box["prompt"] = prompt
        if isinstance(box["answer"], Exception):
            raise box["answer"]
        return box["answer"]

    monkeypatch.setattr(llm, "complete_json", fake)
    return box


GOOD = {
    "name": "Gym Girl",
    "outfits": ["a sage gym set", "leggings with a crop top"],
    "backgrounds": ["free weights area", "mirror wall"],
    "style_vibe": "cool studio light",
    "always_include": "",
    "dressCode": "",
    "scenarios": [{"name": "Squat", "setting": "rack", "action": "fixes her ponytail", "camera": "low angle"}],
    "hooks": ["Train with me?"],
    "themes": [{"name": "Gym crush", "hook": "she notices you"}],
}


@pytest.fixture
def model(client):
    return client.post("/models", json={"name": "Lena", "vibe": "sporty"}).json()
