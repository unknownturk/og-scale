"""Tabellen und Felder — die eine Quelle für Speicher, Airtable-Schema und API.

Jede Tabelle: app-Schlüssel -> (Airtable-Feldname, Art).
Arten: text, long, json, select, number, link (ein verknüpfter Datensatz).
"""

MODELS = "Models"
NICHES = "Niches"

NICHE_STATUS = ("Proposed", "Approved", "Rejected")
NICHE_SOURCE = ("AI", "Brief", "Manual")
NSFW_LEVELS = ("sfw", "spicy", "nsfw")
MARKETS = ("DE", "US")
LANGUAGES = ("German", "English")

TABLES = {
    MODELS: {
        "name": ("Name", "text"),
        "vibe": ("Vibe", "long"),
        "language": ("Language", "select"),
        "market": ("Market", "select"),
        "notes": ("Notes", "long"),
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
}

SELECT_CHOICES = {
    (MODELS, "language"): LANGUAGES,
    (MODELS, "market"): MARKETS,
    (NICHES, "status"): NICHE_STATUS,
    (NICHES, "source"): NICHE_SOURCE,
    (NICHES, "market"): MARKETS,
    (NICHES, "nsfwLevel"): NSFW_LEVELS,
}

# Verknüpfungen: (Tabelle, Schlüssel) -> Zieltabelle
LINKS = {(NICHES, "modelId"): MODELS}

JSON_DEFAULT = []
