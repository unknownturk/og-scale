"""Alle Einstellungen an einer Stelle. Nichts anderes liest os.environ."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes")


BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
CREATIVE_MODEL = os.getenv("CREATIVE_MODEL", "openai/gpt-4o")

_VAR = Path(__file__).resolve().parent.parent / "var"
DATABASE_URL = os.getenv("DATABASE_URL", "") or f"sqlite:///{_VAR / 'og-scale.db'}"

CORS_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
]
DEMO_SEED = _flag("DEMO_SEED")

# Eine Zeitzone für die ganze App — nie datetime.now() ohne sie.
TIMEZONE = ZoneInfo("Europe/Berlin")

# Obergrenzen, damit ein Tippfehler kein Geld verbrennt.
MAX_NICHES_PER_REQUEST = 6


def airtable_configured() -> bool:
    return bool(AIRTABLE_API_KEY and AIRTABLE_BASE_ID)
