"""Prompts für Nischen. Inhaltlich aus dem bisherigen Hub übernommen.

Einzige inhaltliche Änderung: Die Outfit-Regel „alles freizügig" widersprach
der Regel „echte Berufe tragen die echte Uniform". Jetzt gilt die Uniform-Regel
ausdrücklich vor, die Outfit-Liste beschreibt nur den anderen Fall.
"""

FEWSHOT = """
EXAMPLE (for tone & specificity — do NOT copy verbatim):
{
  "name": "US Border Patrol Officer",
  "outfits": [
    "an official border patrol uniform with badges and a duty belt",
    "a fitted tactical polo with cargo pants and aviator sunglasses",
    "a green field jacket over a tank top with a utility belt",
    "a summer short-sleeve patrol shirt with a cap"
  ],
  "backgrounds": [
    "a tactical border checkpoint at dusk with floodlights",
    "the interior of a patrol SUV",
    "a desert outpost with distant mountains",
    "a dusty border road at golden hour"
  ],
  "style_vibe": "high realism, cinematic, authoritative",
  "scenarios": [
    {"name": "Checkpoint", "setting": "tactical border checkpoint at dusk", "action": "leaning on the barrier, searching a vehicle"},
    {"name": "Patrol", "setting": "desert outpost", "action": "adjusting her cap, scanning the horizon"},
    {"name": "Break", "setting": "patrol SUV interior", "action": "sipping coffee, glancing at the camera with a smirk"}
  ],
  "hooks": ["License and registration please... 😉", "POV: you got pulled over by the cutest officer"],
  "themes": [{"name": "Detained Romance", "hook": "treat the viewer like a suspect she's testing"}]
}
"""

REALISM_RULES = (
    "REALISM & WARDROBE RULES (very important — these win over any other outfit instruction):\n"
    "- If the niche is a REAL profession/role with a real-world uniform (police officer, nurse, doctor, "
    'paramedic, flight attendant, soldier, security guard, etc.): set "dressCode":"authentic". Make '
    '"outfits" the ACCURATE, country-correct real uniform (correct colors, patches, insignia exactly as '
    "worn in real life — e.g. a German police officer wears the authentic German 'Polizei' uniform; a nurse "
    'wears real hospital scrubs). Keep "backgrounds" to realistic work locations ONLY (a nurse stays inside '
    "a hospital/clinic; a police officer at a station/street/checkpoint). Put a short clause in "
    '"always_include" naming the authentic uniform and the work setting.\n'
    '- OTHERWISE (lifestyle / spicy / OnlyFans-style niches): set "dressCode":"". Make "outfits" tight, '
    "form-fitting, figure-flattering outfits that show plenty of skin but are strictly SFW (short skirts, "
    "crop tops, fitted dresses, bikinis at the beach) — always tasteful, no nudity, no explicit words.\n"
    "- ALWAYS keep every single word SFW so the image provider's text moderation passes."
)

_OUTFITS = (
    '8-12 DISTINCT outfit TYPES (each a noun phrase, e.g. "a fitted..."). NOT color variants of the\n'
    "  same garment. For a real profession follow the uniform rule below. Otherwise every outfit is revealing\n"
    "  (short, tight, plenty of skin), the way IG/OnlyFans models actually dress: micro minidresses, tiny\n"
    "  hotpants + knotted crop top (bare midriff), mini skirt + cropped tank, tight gym sets (sports bra +\n"
    "  booty shorts), slip dresses, off-shoulder/backless tops, bandeau tops, bikini top + tiny shorts.\n"
    "  Form-flattering, revealing but strictly SFW (clothed, no nudity)."
)

JSON_SHAPE = (
    '{"niches": [ { "name": "...", "outfits": ["...","..."], "backgrounds": ["...","..."], '
    '"dressCode": "" or "authentic", "always_include": "", "style_vibe": "...", '
    '"scenarios": [...], "hooks": [...], "themes": [...] } ]}'
)

_POOLS = f"""- "outfits": {_OUTFITS}
- "backgrounds": 3-5 DISTINCT, concrete, realistic environments.
- "style_vibe": short visual/lighting mood.
- "scenarios": 3-4 objects with "name", "setting" (concrete place) and "action" (a flirty, teasing but SFW movement). Vary settings/actions.
- "hooks": 2-3 scroll-stopping caption hooks in {{language}}.
- "themes": 1-2 objects with "name" and "hook" describing a recurring content angle."""


def proposals(model_name, vibe, count, language):
    return f"""You are a world-class content strategist for AI persona / creator marketing.
Propose {count} DISTINCT, commercially viable Instagram content niches for the model "{model_name}".
Model vibe / description: {vibe or "a stunning, confident female creator"}.

Each niche must be a complete, production-ready spec. IMPORTANT: provide VARIETY
so generated content never looks repetitive — give a POOL of options:
- "name": short, punchy niche title.
{_POOLS.format(language=language)}

Make the outfits and backgrounds genuinely different from each other so random
combinations stay fresh. Keep everything suggestive-but-SFW (no nudity, no explicit terms).

{REALISM_RULES}
{FEWSHOT}

Return ONLY valid JSON, no markdown, in this exact shape:
{JSON_SHAPE}
"""


def from_brief(model_name, brief, language):
    return f"""Build ONE complete, production-ready Instagram content niche for the model "{model_name}",
based on these notes / bullet points from the operator:

\"\"\"{brief}\"\"\"

FOLLOW THE OPERATOR'S BULLET POINTS FAITHFULLY: if they specify exact outfits, a setting,
a profession/uniform or other details, use them VERBATIM (do not water them down). Only fill
genuine gaps. Choose a fitting short "name".
Provide VARIETY (pools) where the notes leave room:
- "name": short fitting niche title.
{_POOLS.format(language=language)}

{REALISM_RULES}
Return ONLY valid JSON, no markdown: {JSON_SHAPE}"""


def improve(model_name, niche_name, hint, language):
    return f"""Create ONE complete Instagram content niche for the model "{model_name}".
The niche is: "{niche_name}". Context/hint: {hint or niche_name}.

Produce a production-ready spec with VARIETY (pools):
- "name": "{niche_name}"
{_POOLS.format(language=language)}

{REALISM_RULES}
Return ONLY valid JSON, no markdown: {JSON_SHAPE}"""
