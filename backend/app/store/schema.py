"""Tabellen und Felder — die eine Quelle für Speicher, Airtable-Schema und API.

Jede Tabelle: app-Schlüssel -> (Airtable-Feldname, Art).
Arten: text, long, json, select, number (ganz), decimal (eine Nachkommastelle), link (ein verknüpfter Datensatz),
attach (Liste von Datei-Adressen; Airtable speichert die Dateien dauerhaft).
"""

MODELS = "Models"
NICHES = "Niches"
CONTENT = "Content"
SOURCES = "Sources"
VIRAL = "Viral Reels"

NICHE_STATUS = ("Proposed", "Approved", "Rejected")
NICHE_SOURCE = ("AI", "Brief", "Manual")
NSFW_LEVELS = ("sfw", "spicy", "nsfw")
MARKETS = ("DE", "US")
LANGUAGES = ("German", "English")
BODY_TYPES = ("normal", "slim", "curvy", "athletic", "busty")
CONTENT_TYPES = ("Carousel", "Photo", "Reel")
# Ein Zustand pro Content: in Arbeit -> wartet auf dich -> freigegeben/abgelehnt.
CONTENT_STATUS = ("Working", "Review", "Approved", "Rejected", "Failed")
CONTENT_STEPS = ("images", "frame", "image", "video")
SOURCE_STATE = ("Active", "Disabled")
VIRAL_STATUS = ("New", "Imported", "Dismissed")
VIDEO_MODELS = ("kling-3.0", "kling-2.6")
PHOTO_MODES = ("niche", "lifestyle", "story_daily", "story_me", "story_cta")

TABLES = {
    MODELS: {
        "name": ("Name", "text"),
        "vibe": ("Vibe", "long"),
        "language": ("Language", "select"),
        "market": ("Market", "select"),
        "notes": ("Notes", "long"),
        "bodyType": ("Body Type", "select"),
        "referenceImages": ("Reference Images", "attach"),
    },
    NICHES: {
        "name": ("Name", "text"),
        "modelId": ("Model", "link"),
        "status": ("Status", "select"),
        "source": ("Source", "select"),
        "market": ("Market", "select"),
        "styleVibe": ("Style Vibe", "long"),
        "outfits": ("Outfits", "json"),
        "backgrounds": ("Backgrounds", "json"),
        "scenarios": ("Scenarios", "json"),
        "hooks": ("Hooks", "json"),
        "themes": ("Themes", "json"),
        "alwaysInclude": ("Always Include", "long"),
        "dressCode": ("Dress Code", "text"),
        "nsfwLevel": ("NSFW Level", "select"),
    },
    CONTENT: {
        "title": ("Title", "text"),
        "modelId": ("Model", "link"),
        "nicheId": ("Niche", "link"),
        "type": ("Type", "select"),
        "status": ("Status", "select"),
        "step": ("Step", "select"),
        "mode": ("Mode", "select"),
        "error": ("Error", "long"),
        "prompt": ("Prompt", "long"),
        "images": ("Images", "attach"),
        # Nur Reels: Vorlage, ihr erstes Bild und das fertige Video.
        "sourceUrl": ("Source URL", "long"),
        "sourceVideo": ("Source Video", "attach"),
        "frame": ("Source Frame", "attach"),
        "finalReel": ("Final Reel", "attach"),
        "videoModel": ("Video Model", "select"),
        # Quittungen der Anbieter-Aufträge: je Platz Phase, Auftragsnummer, Ergebnis.
        "tasks": ("Tasks", "json"),
    },
    # Viral Content: beobachtete Instagram-Accounts und ihre Reels.
    SOURCES: {
        "handle": ("Handle", "text"),
        "market": ("Market", "select"),
        "category": ("Category", "text"),
        "state": ("State", "select"),
        "lastScraped": ("Last Scraped", "text"),
    },
    VIRAL: {
        "reelUrl": ("Reel URL", "text"),
        "owner": ("Owner", "text"),
        "market": ("Market", "select"),
        "category": ("Category", "text"),
        "videoUrl": ("Video URL", "long"),
        "thumbnail": ("Thumbnail", "long"),
        "caption": ("Caption", "long"),
        "likes": ("Likes", "number"),
        "comments": ("Comments", "number"),
        "views": ("Views", "number"),
        "postedAt": ("Posted At", "text"),
        "scrapedAt": ("Scraped At", "text"),
        "viralScore": ("Views per Hour", "decimal"),
        "outperform": ("Outperform", "decimal"),
        "potential": ("Potential", "number"),
        "status": ("Status", "select"),
        "importedContent": ("Imported Content", "json"),
    },
}

SELECT_CHOICES = {
    (MODELS, "language"): LANGUAGES,
    (MODELS, "market"): MARKETS,
    (NICHES, "status"): NICHE_STATUS,
    (NICHES, "source"): NICHE_SOURCE,
    (NICHES, "market"): MARKETS,
    (NICHES, "nsfwLevel"): NSFW_LEVELS,
    (MODELS, "bodyType"): BODY_TYPES,
    (CONTENT, "type"): CONTENT_TYPES,
    (CONTENT, "status"): CONTENT_STATUS,
    (CONTENT, "step"): CONTENT_STEPS,
    (CONTENT, "mode"): PHOTO_MODES,
    (CONTENT, "videoModel"): VIDEO_MODELS,
    (SOURCES, "market"): MARKETS,
    (SOURCES, "state"): SOURCE_STATE,
    (VIRAL, "market"): MARKETS,
    (VIRAL, "status"): VIRAL_STATUS,
}

# Verknüpfungen: (Tabelle, Schlüssel) -> Zieltabelle
LINKS = {(NICHES, "modelId"): MODELS, (CONTENT, "modelId"): MODELS, (CONTENT, "nicheId"): NICHES}

JSON_DEFAULT = []
