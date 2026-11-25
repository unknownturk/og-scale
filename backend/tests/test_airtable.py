"""Der Airtable-Client gegen einen nachgestellten Server (kein Netz nötig)."""

import json

from app.store import NICHES
from app.store.airtable import AirtableStore


class FakeHttp:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        status, body = self.replies.pop(0)

        class R:
            status_code, text = status, json.dumps(body)

            def json(self_inner):
                return body

        return R()


def test_create_maps_fields_and_links(monkeypatch):
    http = FakeHttp([(200, {"id": "recN", "createdTime": "t", "fields": {"Name": "Gym", "Model": ["recM"], "Outfits": '["a"]'}})])
    row = AirtableStore("k", "appX", http).create(NICHES, {"name": "Gym", "modelId": "recM", "outfits": ["a"], "bogus": 1})
    sent = http.calls[0][2]["json"]["fields"]
    assert sent == {"Name": "Gym", "Model": ["recM"], "Model Id": "recM", "Outfits": '["a"]'}
    assert row["modelId"] == "recM" and row["outfits"] == ["a"] and row["hooks"] == []


def test_list_filters_pages_and_retries(monkeypatch):
    monkeypatch.setattr("app.store.airtable.time.sleep", lambda s: None)
    http = FakeHttp([
        (429, {}),
        (200, {"records": [{"id": "r1", "createdTime": "1", "fields": {}}], "offset": "o"}),
        (200, {"records": [{"id": "r2", "createdTime": "2", "fields": {}}]}),
    ])
    rows = AirtableStore("k", "appX", http).list(NICHES, {"modelId": "rec'M"})
    assert [r["id"] for r in rows] == ["r1", "r2"]
    assert http.calls[1][2]["params"]["filterByFormula"] == "{Model Id}='rec\\'M'"
    assert http.calls[2][2]["params"]["offset"] == "o"
