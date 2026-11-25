"""Beispieldaten für den Demo-Speicher (nur mit DEMO_SEED=1, nie in Airtable)."""

from . import settings
from .store import MODELS, NICHES


def seed(store):
    if store.kind != "memory" or store.list(MODELS):
        return
    lena = store.create(MODELS, {"name": "Lena Hartmann", "vibe": "Sportliche Blondine aus München, frech, nahbar, lacht viel.", "language": "German", "market": "DE", "notes": ""})
    store.create(MODELS, {"name": "Mia Carter", "vibe": "Sun-kissed California girl, confident and playful.", "language": "English", "market": "US", "notes": ""})
    if settings.MEDIA_PROVIDER == "fake":
        from .media import get_provider
        from .media.fake import _png

        refs = [get_provider().host_file(_png(f"lena-{i}", 300, 380), "ref.png") for i in range(3)]
        store.update(MODELS, lena["id"], {"referenceImages": refs, "bodyType": "athletic"})
    reel_niche = None
    base = {"modelId": lena["id"], "market": "DE", "source": "AI", "themes": [], "alwaysInclude": "", "dressCode": "", "nsfwLevel": "sfw"}
    reel_niche = store.create(NICHES, {**base, "name": "Tankstelle bei Nacht", "status": "Approved", "styleVibe": "Neonlicht, nasser Asphalt, filmisch",
        "outfits": ["ein kurzes Jeanskleid mit Gürtel", "Hotpants mit geknotetem Crop-Top", "ein enges Minikleid in Rot", "Sport-BH mit Radlerhose", "ein Slipdress mit Lederjacke"],
        "backgrounds": ["eine Zapfsäule unter Neonröhren", "der Shop mit Kühlregal", "ein Parkplatz im Regen"],
        "scenarios": [{"name": "Tanken", "setting": "Zapfsäule", "action": "lehnt am Auto und schaut über die Schulter"}],
        "hooks": ["POV: Du wolltest nur kurz tanken", "Wer zahlt heute meinen Tank? 😇"]})
    store.create(NICHES, {**base, "name": "Notaufnahme-Schicht", "status": "Proposed", "dressCode": "authentic", "alwaysInclude": "echte Klinik-Kasacks, Krankenhausumgebung", "styleVibe": "helles Kliniklicht, dokumentarisch",
        "outfits": ["ein blauer Kasack mit Namensschild", "ein grüner OP-Kittel mit Haube", "ein weißer Kasack mit Stethoskop"],
        "backgrounds": ["ein Stationsflur", "ein Schwesternzimmer mit Monitoren", "ein Behandlungsraum"],
        "scenarios": [{"name": "Übergabe", "setting": "Schwesternzimmer", "action": "blättert in der Akte und zwinkert"}],
        "hooks": ["Deine Nachtschwester hat heute Geduld", "POV: Ich messe deinen Puls"]})
    store.create(NICHES, {**base, "name": "Gym Girl", "status": "Proposed", "styleVibe": "kühles Studiolicht, Spiegel, dynamisch",
        "outfits": ["ein Set aus Sport-BH und Shorts in Salbei", "Leggings mit bauchfreiem Top", "ein Einteiler mit Rückenausschnitt", "Radlerhose mit Bandeau"],
        "backgrounds": ["der Freihantelbereich", "eine Spiegelwand", "die Umkleide"],
        "scenarios": [{"name": "Squat", "setting": "Rack", "action": "richtet den Zopf und grinst in den Spiegel"}],
        "hooks": ["Trainierst du mit mir?", "Er meinte, er spottet nur 🙄"]})
    store.create(NICHES, {**base, "name": "Büro nach Feierabend", "status": "Rejected", "styleVibe": "warmes Schreibtischlicht",
        "outfits": ["ein Bleistiftrock mit Bluse"], "backgrounds": ["ein leeres Großraumbüro"], "scenarios": [], "hooks": []})
    if settings.MEDIA_PROVIDER == "fake" and reel_niche:
        from .media.fake import _png, _silent_clip
        from .store import CONTENT

        for i in range(1, 5):  # vier freigegebene Reels als Vorrat für AliRemote
            store.create(CONTENT, {
                "title": f"Reel {i}: Tankstelle bei Nacht", "modelId": lena["id"], "nicheId": reel_niche["id"], "type": "Reel",
                "status": "Approved", "step": "video", "error": "", "videoModel": "kling-3.0", "tasks": {},
                "images": [get_provider().host_file(_png(f"reel{i}", 270, 480), "bild.png")],
                "frame": [], "sourceVideo": [], "finalReel": [get_provider().host_file(_silent_clip(f"reel{i}"), "reel.mp4")],
            })
