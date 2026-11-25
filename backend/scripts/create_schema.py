"""Legt die Tabellen in der (neuen, leeren) Airtable-Base an.

    python -m scripts.create_schema

Mehrfaches Ausführen ist harmlos: vorhandene Tabellen werden übersprungen.
Der Airtable-Token braucht die Rechte schema.bases:read und schema.bases:write.
"""

import sys

import requests

from app import settings
from app.store.schema import LINKS, SELECT_CHOICES, TABLES

_META = "https://api.airtable.com/v0/meta/bases"


def _field(table, key, name, kind, table_ids):
    if kind == "text":
        return [{"name": name, "type": "singleLineText"}]
    if kind in ("long", "json"):
        return [{"name": name, "type": "multilineText"}]
    if kind == "number":
        return [{"name": name, "type": "number", "options": {"precision": 0}}]
    if kind == "select":
        choices = [{"name": c} for c in SELECT_CHOICES[(table, key)]]
        return [{"name": name, "type": "singleSelect", "options": {"choices": choices}}]
    if kind == "link":
        target = table_ids[LINKS[(table, key)]]
        return [
            {
                "name": name,
                "type": "multipleRecordLinks",
                "options": {"linkedTableId": target},
            },
            {"name": f"{name} Id", "type": "singleLineText"},
        ]
    raise ValueError(kind)


def main():
    if not settings.airtable_configured():
        sys.exit("AIRTABLE_API_KEY und AIRTABLE_BASE_ID müssen gesetzt sein.")
    url = f"{_META}/{settings.AIRTABLE_BASE_ID}/tables"
    headers = {"Authorization": f"Bearer {settings.AIRTABLE_API_KEY}"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    table_ids = {t["name"]: t["id"] for t in resp.json().get("tables", [])}
    for table, fields in TABLES.items():  # Reihenfolge: Ziel einer Verknüpfung zuerst
        if table in table_ids:
            print(f"vorhanden: {table}")
            continue
        specs = []
        for key, (name, kind) in fields.items():
            specs += _field(table, key, name, kind, table_ids)
        # Airtable verlangt ein Textfeld als erstes Feld.
        specs.sort(key=lambda f: f["name"] != "Name")
        resp = requests.post(
            url, headers=headers, json={"name": table, "fields": specs}, timeout=30
        )
        if resp.status_code >= 400:
            sys.exit(f"Fehler bei {table}: {resp.status_code} {resp.text[:300]}")
        table_ids[table] = resp.json()["id"]
        print(f"angelegt: {table}")


if __name__ == "__main__":
    main()
