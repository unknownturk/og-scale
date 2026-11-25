"""Airtable als Datenbank. Kleiner Client: Timeout, Wiederholung bei 429/5xx,
Seitenweise Lesen. Übersetzt zwischen App-Schlüsseln und Airtable-Feldern."""

import json
import time
from urllib.parse import quote

import requests

from .. import settings
from .memory import NotFound
from .schema import LINKS, TABLES

_API = "https://api.airtable.com/v0"
_TIMEOUT = 30
_RETRY_STATUS = {429, 500, 502, 503, 504}


class AirtableError(RuntimeError):
    pass


class AirtableStore:
    kind = "airtable"

    def __init__(self, api_key=None, base_id=None, session=None):
        self._key = api_key or settings.AIRTABLE_API_KEY
        self._base = base_id or settings.AIRTABLE_BASE_ID
        self._http = session or requests.Session()
        self._attachment_ids = {}  # Datei-Adresse -> Airtable-Datei-Id

    # --- HTTP ---------------------------------------------------------------
    def _request(self, method, url, **kwargs):
        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        last = None
        for attempt in range(4):
            try:
                resp = self._http.request(
                    method, url, headers=headers, timeout=_TIMEOUT, **kwargs
                )
            except requests.RequestException as exc:
                last = exc
            else:
                if resp.status_code == 404:
                    raise NotFound(url)
                if resp.status_code not in _RETRY_STATUS:
                    if resp.status_code >= 400:
                        raise AirtableError(
                            f"Airtable {resp.status_code}: {resp.text[:300]}"
                        )
                    return resp.json()
                last = AirtableError(f"Airtable {resp.status_code}")
            time.sleep(0.5 * (2**attempt))
        raise AirtableError(f"Airtable nicht erreichbar: {last}")

    def _url(self, table, record_id=None):
        url = f"{_API}/{self._base}/{quote(table)}"
        return f"{url}/{record_id}" if record_id else url

    # --- Übersetzung --------------------------------------------------------
    def _to_fields(self, table, data):
        out = {}
        for key, value in data.items():
            if key not in TABLES[table]:
                continue
            name, kind = TABLES[table][key]
            if kind == "json":
                out[name] = json.dumps(
                    value if value is not None else [], ensure_ascii=False
                )
            elif kind == "link":
                out[name] = [value] if value else []
                out[f"{name} Id"] = value or ""
            elif kind == "attach":
                # Schon gespeicherte Dateien per Id behalten, statt sie neu hochzuladen.
                out[name] = [
                    {"id": self._attachment_ids[url]} if url in self._attachment_ids else {"url": url}
                    for url in (value or [])
                ]
            else:
                out[name] = value
        return out

    def _from_record(self, table, record):
        fields = record.get("fields", {})
        row = {"id": record["id"], "created": record.get("createdTime")}
        for key, (name, kind) in TABLES[table].items():
            raw = fields.get(name)
            if kind == "json":
                try:
                    row[key] = json.loads(raw) if raw else []
                except (TypeError, ValueError):
                    row[key] = []
            elif kind == "link":
                row[key] = (raw or [None])[0]
            elif kind == "attach":
                row[key] = []
                for a in raw or []:
                    if a.get("url"):
                        row[key].append(a["url"])
                        if a.get("id"):
                            self._attachment_ids[a["url"]] = a["id"]
            elif kind == "number":
                row[key] = raw or 0
            else:
                row[key] = raw or ""
        return row

    # --- Speicher-Schnittstelle --------------------------------------------
    def list(self, table, where=None):
        params = {"pageSize": 100}
        clauses = []
        for key, value in (where or {}).items():
            name, kind = TABLES[table][key]
            field = f"{name} Id" if kind == "link" else name
            safe = str(value).replace("\\", "\\\\").replace("'", "\\'")
            clauses.append(f"{{{field}}}='{safe}'")
        if clauses:
            params["filterByFormula"] = (
                clauses[0] if len(clauses) == 1 else f"AND({','.join(clauses)})"
            )
        rows, offset = [], None
        while True:
            if offset:
                params["offset"] = offset
            page = self._request("GET", self._url(table), params=params)
            rows += [self._from_record(table, r) for r in page.get("records", [])]
            offset = page.get("offset")
            if not offset:
                break
        return sorted(rows, key=lambda r: r["created"] or "")

    def get(self, table, record_id):
        return self._from_record(
            table, self._request("GET", self._url(table, record_id))
        )

    def create(self, table, fields):
        body = {"fields": self._to_fields(table, fields), "typecast": False}
        return self._from_record(
            table, self._request("POST", self._url(table), json=body)
        )

    def update(self, table, record_id, fields):
        body = {"fields": self._to_fields(table, fields), "typecast": False}
        return self._from_record(
            table, self._request("PATCH", self._url(table, record_id), json=body)
        )

    def delete(self, table, record_id):
        self._request("DELETE", self._url(table, record_id))


def link_id_field(table, key):
    """Name des Textfelds, das die Id einer Verknüpfung filterbar macht."""
    assert (table, key) in LINKS
    return f"{TABLES[table][key][0]} Id"
