"""Datenspeicher. Airtable, wenn konfiguriert — sonst ein flüchtiger Demo-Speicher."""

from .. import settings
from .memory import MemoryStore, NotFound  # noqa: F401
from .schema import CONTENT, MODELS, NICHES  # noqa: F401

_store = None


def get_store():
    global _store
    if _store is None:
        if settings.airtable_configured():
            from .airtable import AirtableStore

            _store = AirtableStore()
        else:
            _store = MemoryStore()
    return _store


def set_store(store):
    """Für Tests."""
    global _store
    _store = store
