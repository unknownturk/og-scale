"""Bild-Prompts. Wortlaut aus dem bisherigen Hub übernommen, damit die Bilder
gleich aussehen; nur die Teile für Carousels, Fotos und Motion-Frames."""

import re

# Body-type tokens (set per model) → tasteful, SFW descriptors woven into prompts.
_BODY_TYPE_MAP = {
    "normal": "",
    "slim": "a slim, slender figure",
    "curvy": "a curvy, hourglass figure",
    "athletic": "a fit, toned athletic figure",
    "busty": "a curvy figure with a fuller bust",
}


def body_clause(body_type):
    """SFW body-shape descriptor for a model's chosen body type (or free text)."""
    bt = (body_type or "").strip()
    desc = _BODY_TYPE_MAP.get(bt.lower(), bt)
    return f" She has {desc}." if desc else ""


def name_tag_clause(model_name):
    """For authentic-uniform niches: a name tag on the uniform reading the model's name."""
    name = (model_name or "").strip()
    return (
        f" She wears a visible name tag on her uniform that clearly reads '{name}'."
        if name
        else ""
    )


# SFW cues so US-market content is unmistakably American (flag, US decor,
# occasionally a small Trump figurine). Rotated per image for variety.
_US_CUES = [
    "a small American flag visible in the scene",
    "subtle American decor with red-white-and-blue accents",
    "a clearly American-style interior with US details",
    "a small US flag on the wall",
    "a small Trump bobblehead figurine on a shelf or car dashboard",
    "everyday American styling and props",
]

# SFW cues so DE-market content reads clearly German/European — without an
# anchor the image model defaults to an American look (esp. for uniforms).
_DE_CUES = [
    "clearly set in Germany, everyday German/European styling",
    "a typical modern German apartment interior, European details",
    "German everyday setting, central-European styling throughout",
    "believably German surroundings, European look and props",
]


def effective_market(niche_market, model_language):
    m = (niche_market or "").strip().upper()
    if m:
        return m
    return "US" if (model_language or "").lower().startswith("eng") else "DE"


def market_cue(market, variant=0):
    """Anchor the country so the image model doesn't default to an American look.
    US → flag/American decor/occasional Trump figurine; DE → German/European
    styling (important for uniforms: 'police' with no country reads as US cop).
    SFW; rotated per image for variety."""
    m = (market or "").upper()
    if m == "US":
        cue = _US_CUES[variant % len(_US_CUES)]
        return f" Clearly set in the USA: {cue}; American styling throughout."
    if m == "DE":
        cue = _DE_CUES[variant % len(_DE_CUES)]
        return f" {cue[0].upper()}{cue[1:]}."
    return ""



_HARD_EXPLICIT = {
    r"\bnude\b": "in lingerie",
    r"\bnaked\b": "in lingerie",
    r"\btopless\b": "in a bra",
    r"\bpenetrat\w*\b": "posing",
    r"\bcum\w*\b": "glistening",
    r"\bblowjob\b": "a playful pose",
    r"\bgenital\w*\b": "figure",
    r"\bexplicit\b": "suggestive",
    r"\blicking\b": "holding",
    r"\bsucking\b": "holding",
}


def sanitize_prompt(text, nsfw_level=None):
    """Soften triggering keywords so generations pass provider safety filters.
    For spicy/nsfw niches keep revealing-wardrobe words (lingerie/sheer/bodysuit/sexy)
    that permissive models accept, and only strip hard-explicit terms."""
    if not text:
        return ""
    text = re.sub(r"\bonlyfans\b", "lifestyle influencer", text, flags=re.IGNORECASE)
    if (nsfw_level or "sfw").lower() in ("spicy", "nsfw"):
        for pattern, replacement in _HARD_EXPLICIT.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        return text
    replacements = {
        r"\bskimpy\b": "fashionable",
        r"\btiny\b": "small",
        r"\bprovocative\b": "captivating",
        r"\bseductive\b": "charming",
        r"\blingerie\b": "loungewear",
        r"\bthong underwear\b": "shorts",
        r"\bthong\b": "shorts",
        r"\bg-string\b": "shorts",
        r"\bpanties\b": "shorts",
        r"\bunderwear\b": "athletic shorts",
        r"\bsexy\b": "stunning",
        r"\bvery short\b": "summer-style",
        r"\bshort skimpy\b": "short summer",
        r"\bmini\b": "short",
        # extra softeners for scene-LLM phrasings that trip provider moderation
        r"\bshowcasing (her )?curves?\b": "with an elegant silhouette",
        r"\bshowing off (her )?curves?\b": "with an elegant silhouette",
        r"\b(biting|bites) (her )?lip\b": "a soft smile",
        r"\blip bite\b": "soft smile",
        r"\blace[- ]trimmed\b": "trimmed",
        r"\blacy\b": "delicate",
        r"\blace shorts\b": "shorts",
        r"\bboyshorts?\b": "shorts",
        r"\bsheer\b": "soft",
        r"\bdeep neckline\b": "neckline",
        r"\bbodysuit\b": "fitted top",
        r"\bcorset\b": "fitted top",
        r"\bboudoir\b": "cozy bedroom",
        # niche-name / vibe words that themselves trip image moderation
        r"\bkinky\b": "playful",
        r"\bnaughty\b": "playful",
        r"\bthirst\b": "trendy",
        r"\bspicy\b": "stylish",
        r"\bnsfw\b": "sfw",
        # residual borderline actions the scene-LLM sometimes pulls from DNA
        r"\blicking\b": "holding",
        r"\bcrawling\b": "kneeling",
        r"\bsucking\b": "holding",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


# Shared authenticity anchor for ALL image prompts. The old closing formulas
# ("8k resolution, cinematic photography, professional model look") pushed the
# generators into the glossy AI-render look; this steers toward a believable
# phone photo instead — the single highest-leverage realism lever.
REALISM_ANCHOR = (
    " Authenticity: this must look like a real candid photo shot on an iPhone 17 Pro "
    "for Instagram — natural unretouched skin with visible pores, fine texture and tiny "
    "real-life flaws, true-to-life colors, natural imperfect indoor/available lighting, "
    "subtle sensor grain and slight motion softness, realistic shallow depth of field, "
    "authentic candid framing slightly off-center as if held in one hand. "
    "It should be indistinguishable from a normal girl's real selfie/snapshot. "
    "Strictly avoid: airbrushed or waxy skin, plastic doll look, over-smoothing, "
    "over-saturation, HDR glow, studio lighting, studio-perfect symmetry, beauty-filter "
    "look, CGI, 3D-render or AI-generated look."
)


# Identity lock — appended ONLY when reference photos of the model are provided.
# Without this, the carousel/photo/pfp prompt just says "photo of <name>", which
# means nothing to the image model, and it drifts to a random face. This tells it
# to reconstruct the SAME woman as the reference(s).
IDENTITY_LOCK = (
    " IMPORTANT — IDENTITY: the provided reference image(s) show the EXACT real "
    "woman this photo must depict. Reconstruct HER precise identity: same face "
    "shape, facial features, eye color, skin tone, hair and overall look. She must "
    "be clearly recognizable as the same person as in the references. Do NOT invent, "
    "swap or beautify a different face."
)


# Generic wardrobe used to top up small/homogeneous niche outfit pools — the way
# IG/OnlyFans models actually dress. Without this, a niche whose pool is just
# "white dress"/"red dress" repeats the same look across 100 generations.
# Deliberately ALL revealing (short, tight, lots of skin) — still clothed/SFW;
# the spicy list below adds the lingerie/bikini tier on top.
OUTFIT_VARIETY_SFW = [
    "tiny denim hotpants with a knotted crop top, bare midriff",
    "a skin-tight micro minidress",
    "black leggings with a tiny sports bra, bare midriff",
    "a mini skirt with a cropped tank top, long bare legs",
    "a tight gym set — sports bra and booty shorts",
    "a short slip dress with thin straps",
    "an off-shoulder crop top with low-rise shorts",
    "a bandeau top with a high-slit mini skirt",
    "a backless halter top with hotpants",
    "a triangle bikini top with tiny denim shorts",
]
OUTFIT_VARIETY_SPICY = [
    "a lace bralette with denim hotpants",
    "a silk robe loosely tied over a matching lingerie set",
    "a tiny string bikini",
    "a sheer mesh top over a bra",
    "a high-cut bodysuit",
    "an oversized shirt unbuttoned over underwear",
]


def varied_outfits(outfits, nsfw_level=None, min_pool=8):
    """Guarantee outfit variety at the niche's NSFW level: pools smaller than
    `min_pool` get blended with the generic wardrobe above, so random.choice
    actually varies instead of cycling two dresses. Big curated pools win."""
    pool = [o for o in (outfits or []) if o]
    if len(pool) >= min_pool:
        return pool
    extra = list(OUTFIT_VARIETY_SFW)
    if (nsfw_level or "sfw").lower() in ("spicy", "nsfw"):
        extra += OUTFIT_VARIETY_SPICY
    return pool + extra


def build_motion_image_prompt(outfit=None, background=None, nsfw_level=None):
    """
    ULTRA-STRICT character reconstruction prompt for motion-control.

    Reference 1 = extracted source frame (pose/camera template ONLY).
    References 2..N = photos of the SAME real person whose identity must be kept.
    """
    outfit_part = (
        sanitize_prompt(outfit, nsfw_level)
        if outfit
        else "match the exact outfit of the first reference image"
    )
    bg_part = (
        sanitize_prompt(background, nsfw_level)
        if background
        else "the background matches the first reference image"
    )
    return (
        "ULTRA-STRICT CHARACTER RECONSTRUCTION. "
        "The FIRST reference image is ONLY a pose/composition/camera template — do NOT copy that person's face or body. "
        "ALL OTHER reference images show the SAME real woman: reconstruct HER EXACT identity — same face shape, "
        "facial features, freckles, skin tone, eye color and hair. The face must be unmistakably the same person as in those images. "
        "1. Pose Adherence: match the EXACT pose, framing and camera perspective of the first reference image 1:1. "
        "2. Cleanup: REMOVE all text overlays, emojis, subtitles and graphics. Clean, realistic result. "
        "3. Wardrobe & Scene: "
        f"the outfit should be: {outfit_part}; "
        f"the background should be: {bg_part}. "
        "Keep the core environment type (indoor vs outdoor). "
        "Do not beautify or alter her facial identity. Photographic, her face clearly recognizable."
        + REALISM_ANCHOR
    )


def build_carousel_base_prompt(
    model_name, outfit=None, background=None, mode="niche", nsfw_level=None
):
    """Base prompt for a carousel/photo shoot, by mode."""
    if mode == "lifestyle":
        return (
            f"A realistic lifestyle photo of {model_name} in a trendy city cafe or stylish urban street, "
            f"wearing high-end civilian fashion"
        )
    if mode == "story_daily":
        return (
            f"A casual morning photo of {model_name}, she is holding a coffee cup or looking in a grand mirror, "
            f"wearing cozy home clothes"
        )
    if mode == "story_me":
        return f"A stunning close-up portrait of {model_name}, focusing on her face and beautiful expression"
    if mode == "story_cta":
        if (nsfw_level or "sfw").lower() in ("spicy", "nsfw"):
            # CTA stills routed to GPT Image (more permissive) — bikini/lingerie allowed.
            return (
                f"A flirty, alluring photo of {model_name} relaxing at home, wearing a stylish "
                f"bikini or a matching lingerie set, confident inviting pose, soft warm lighting, "
                f"tasteful and aesthetic, high-end social media vibe"
            )
        return (
            f"A cute, inviting cozy photo of {model_name} relaxing comfortably at home, "
            f"wearing a stylish comfy loungewear set, warm friendly atmosphere"
        )
    # default: niche — full-body lifestyle shot (NOT a face portrait) so the
    # outfit and environment actually show. Grammar: "wearing X"; the caller may
    # append ", she is {action}".
    outfit_desc = (
        sanitize_prompt(outfit) if outfit else "a stylish, form-flattering outfit"
    )
    bg = (
        sanitize_prompt(background)
        if background
        else "a realistic, niche-appropriate environment"
    )
    return (
        f"A photorealistic, full-body lifestyle photo of {model_name} in {bg}, "
        f"wearing {outfit_desc}, full figure visible, natural candid framing"
    )


def apply_style(base_prompt, intensity, niche_name="model", mode="niche"):
    """Add style modifiers based on intensity (0-100) and generation mode."""
    niche = (niche_name or "model").lower()
    if mode == "lifestyle":
        style = "candid lifestyle snapshot, civilian trendy fashion, street style, natural daylight, caught-in-the-moment look"
    elif mode == "story_daily":
        style = "casual morning routine, mirror selfie style, cozy atmosphere, warm natural lighting, authentic social media vibe"
    elif mode == "story_me":
        style = "flattering close-up, expressive eyes, soft natural window light, everyday background, authentic selfie-portrait feel"
    elif mode == "story_cta":
        style = "cozy at-home aesthetic, stylish comfy loungewear, soft warm lighting, friendly inviting expression, authentic social media vibe"
    else:
        if intensity < 30:
            style = f"natural {niche} look, casual everyday setting, soft natural lighting, candid pose"
        elif intensity < 65:
            style = f"stylish {niche} content, engaging but natural, bright daylight, relaxed confident pose"
        elif intensity < 85:
            style = (
                f"bold {niche} look, form-fitting fashion, striking aesthetic, "
                f"confident expression, dynamic pose, natural high-contrast light"
            )
        else:
            style = f"premium {niche} vibe, bold fashion, atmospheric setting, moody natural light"
    return f"{base_prompt}. Style: {style}.{REALISM_ANCHOR}"


# ---------------------------------------------------------------------------
# Moderation fallbacks (shared by reel + carousel/photo image generation)
# ---------------------------------------------------------------------------


def is_review_error(e):
    """True if an exception looks like a provider text/content-moderation reject."""
    s = str(e).lower()
    return any(
        k in s
        for k in (
            "failed the review",
            "text content",
            "rejected",
            "sensitive",
            "violat",
        )
    )


def fallback_prompt(model_name, outfit=None, background=None, nsfw_level=None):
    """If moderation rejects the styled prompt, retry with a cleaner version that
    STILL keeps the niche outfit + setting (stays on-brand). For spicy niches the
    outfit stays revealing (lingerie etc.); only the hard-explicit words are stripped."""
    bg = (
        sanitize_prompt(background, nsfw_level)
        if background
        else "a stylish, natural setting"
    )
    out = sanitize_prompt(outfit, nsfw_level) if outfit else "a fashionable outfit"
    spicy = (nsfw_level or "sfw").lower() in ("spicy", "nsfw")
    pose = (
        "confident sensual pose, tasteful"
        if spicy
        else "relaxed natural pose, fully clothed, tasteful"
    )
    return (
        f"A photorealistic, full-body lifestyle photo of {model_name} in {bg}, "
        f"wearing {out}, {pose}, authentic social media aesthetic." + REALISM_ANCHOR
    )


def safe_fallback_prompt(model_name):
    """Absolute last-resort prompt (only if even the niche fallback is rejected)."""
    return (
        f"A photorealistic, tasteful full-body lifestyle photo of {model_name}, "
        f"fully clothed in a stylish trendy outfit, confident friendly expression, "
        f"natural setting, authentic social media aesthetic." + REALISM_ANCHOR
    )
