import pytest
import requests

from app import jobs, llm, settings


class Resp:
    def __init__(self, status=200, content=None, finish="stop", body=None):
        self.status_code, self.text = status, "err"
        self._body = body if body is not None else {"choices": [{"finish_reason": finish, "message": {"content": content}}]}

    def json(self):
        return self._body


@pytest.fixture
def post(monkeypatch):
    monkeypatch.setattr(settings, "OPENROUTER_API_KEY", "k")
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)
    queue = []

    def fake(payload, timeout):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(llm, "_post", fake)
    return queue


def test_parse_repairs_fences_and_trailing_commas():
    assert llm.parse_json('```json\n{"a": [1, 2,],}\n```') == {"a": [1, 2]}
    with pytest.raises(llm.LLMError):
        llm.parse_json("sorry, no")


def test_retries_after_timeout_then_succeeds(post):
    post += [requests.Timeout(), Resp(content='{"ok": true}')]
    assert llm.complete_json("x") == {"ok": True}


@pytest.mark.parametrize("bad", [Resp(body={}), Resp(content=None), Resp(content="{}", finish="length"), Resp(status=500)])
def test_bad_answers_raise_instead_of_returning_garbage(post, bad):
    post += [bad, bad]
    with pytest.raises(llm.LLMError):
        llm.complete_json("x")


def test_rejected_key_is_not_retried(post):
    post += [Resp(status=401)]
    with pytest.raises(llm.LLMError, match="Schlüssel"):
        llm.complete_json("x")
    assert post == []


def test_recover_fails_interrupted_jobs_and_resumes_resumable():
    jobs.init("sqlite:///:memory:")
    ran = []
    jobs.handler("t_plain")(lambda p: ran.append("plain"))
    jobs.handler("t_resume", resume=True)(lambda p: ran.append("resume") or {"done": True})
    with jobs._Session() as s:
        s.add(jobs.Job(id="a", kind="t_plain", status=jobs.RUNNING))
        s.add(jobs.Job(id="b", kind="t_resume", status=jobs.RUNNING))
        s.commit()
    assert jobs.recover() == {"resumed": 1, "failed": 1}
    jobs._pool.submit(lambda: None).result()
    import time
    for _ in range(50):
        if jobs.get("b")["status"] == jobs.SUCCEEDED:
            break
        time.sleep(0.02)
    assert jobs.get("a")["status"] == jobs.FAILED and "Neustart" in jobs.get("a")["error"]
    assert jobs.get("b")["status"] == jobs.SUCCEEDED and ran == ["resume"]
