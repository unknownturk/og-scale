"""Flüchtiger Speicher für Tests und lokales Ausprobieren ohne Airtable."""

import copy
import threading
import uuid
from datetime import datetime, timezone

from .schema import TABLES


class NotFound(KeyError):
    pass


class MemoryStore:
    kind = "memory"

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {table: {} for table in TABLES}

    def _clean(self, table, fields):
        allowed = TABLES[table]
        return {k: copy.deepcopy(v) for k, v in fields.items() if k in allowed}

    def list(self, table, where=None):
        with self._lock:
            rows = [copy.deepcopy(r) for r in self._data[table].values()]
        for key, value in (where or {}).items():
            rows = [r for r in rows if r.get(key) == value]
        return sorted(rows, key=lambda r: r["created"])

    def get(self, table, record_id):
        with self._lock:
            row = self._data[table].get(record_id)
            if row is None:
                raise NotFound(record_id)
            return copy.deepcopy(row)

    def create(self, table, fields):
        row = self._clean(table, fields)
        row["id"] = "rec" + uuid.uuid4().hex[:14]
        row["created"] = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._data[table][row["id"]] = row
        return copy.deepcopy(row)

    def update(self, table, record_id, fields):
        with self._lock:
            row = self._data[table].get(record_id)
            if row is None:
                raise NotFound(record_id)
            row.update(self._clean(table, fields))
            return copy.deepcopy(row)

    def delete(self, table, record_id):
        with self._lock:
            if self._data[table].pop(record_id, None) is None:
                raise NotFound(record_id)
