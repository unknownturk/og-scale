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

# Bild- und Video-Erzeugung. "fake" erzeugt Platzhalter ohne Kosten (nur zum
# Ausprobieren und für Tests) und ist nie die Vorgabe.
KIE_API_KEY = os.getenv("KIE_API_KEY", "")
MEDIA_PROVIDER = os.getenv("MEDIA_PROVIDER", "kie").strip().lower()
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")

# Viral Content: Reels fremder Accounts lesen. HikerAPI hat Vorrang vor Apify.
HIKERAPI_TOKEN = os.getenv("HIKERAPI_TOKEN", "")
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
APIFY_REEL_ACTOR = os.getenv("APIFY_REEL_ACTOR", "apify~instagram-reel-scraper")
VIRAL_NEWER_THAN = os.getenv("VIRAL_NEWER_THAN", "14 days")
VIRAL_RESULTS_LIMIT = int(os.getenv("VIRAL_RESULTS_LIMIT", "20"))
VIRAL_RETENTION_DAYS = int(os.getenv("VIRAL_RETENTION_DAYS", "7"))
# Alle wie viele Stunden von selbst neu gelesen wird (0 = nur von Hand).
VIRAL_AUTO_HOURS = int(os.getenv("VIRAL_AUTO_HOURS", "48"))
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
MAX_IMAGES_PER_REQUEST = 10
MAX_REFERENCE_IMAGES = 6
MAX_UPLOAD_BYTES = 12 * 1024 * 1024

# Warten auf den Anbieter: Abstand zwischen zwei Abfragen und Höchstdauer.
POLL_SECONDS = 5
IMAGE_WAIT_SECONDS = 20 * 60
VIDEO_WAIT_SECONDS = 20 * 60

# Motion-Reels
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")
MAX_REELS_PER_REQUEST = 10
MAX_VIRAL_IMPORT = 30  # Reels, die ein Import höchstens startet (Vorlagen mal Varianten)
MAX_SOURCE_BYTES = 200 * 1024 * 1024
MAX_SOURCE_SECONDS = 30
# Nur für Tests und den Platzhalter-Anbieter: Vorlagen von lokalen Adressen erlauben.
ALLOW_PRIVATE_URLS = _flag("ALLOW_PRIVATE_URLS") or MEDIA_PROVIDER == "fake"
WORK_DIR = _VAR / "work"

FILES_DIR = _VAR / "files"


def airtable_configured() -> bool:
    return bool(AIRTABLE_API_KEY and AIRTABLE_BASE_ID)
