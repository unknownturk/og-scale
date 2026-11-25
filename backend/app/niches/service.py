"""Nischen: erzeugen, prüfen, speichern.

Regeln, die der alte Hub nicht hatte:
- KI-Antworten werden geprüft, bevor irgendetwas gespeichert wird.
- „Verbessern" liefert nur einen Vorschlag; gespeichert wird erst nach Bestätigung.
- Es wird alles oder nichts angelegt — kein halber Stapel bei einem Fehler.
"""

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .. import llm, settings
from ..store import MODELS, NICHES, get_store
from ..store.schema import NSFW_LEVELS
from . import prompts


class NicheError(ValueError):
    pass


class Scenario(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = ""
    setting: str = ""
    action: str = ""


class Theme(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str = ""
    hook: str = ""


def _strings(value):
    if isinstance(value, str):
        value = [value]
    return [str(v).strip() for v in (value or []) if str(v).strip()]


class NicheSpec(BaseModel):
    """Was eine Nische mindestens haben muss, damit daraus Content entstehen kann."""

    name: str = Field(min_length=1, max_length=120)
    outfits: list[str] = Field(min_length=1)
    backgrounds: list[str] = Field(min_length=1)
    styleVibe: str = ""
    scenarios: list[Scenario] = []
    hooks: list[str] = []
    themes: list[Theme] = []
    alwaysInclude: str = ""
    dressCode: str = ""
    nsfwLevel: str = "sfw"

    @field_validator("outfits", "backgrounds", "hooks", mode="before")
    @classmethod
    def _clean_lists(cls, value):
        return _strings(value)

    @field_validator("dressCode", mode="before")
    @classmethod
    def _dress(cls, value):
        return "authentic" if str(value or "").strip().lower() == "authentic" else ""

    @field_validator("nsfwLevel", mode="before")
    @classmethod
    def _nsfw(cls, value):
        value = str(value or "sfw").strip().lower()
        return value if value in NSFW_LEVELS else "sfw"


_ALIASES = {
    "style_vibe": "styleVibe",
    "always_include": "alwaysInclude",
    "dress_code": "dressCode",
}


def validate(raw) -> dict:
    """Eine rohe KI-Nische in eine geprüfte Nische verwandeln oder NicheError werfen."""
    if not isinstance(raw, dict):
        raise NicheError("Die KI hat keine Nische geliefert")
    data = {_ALIASES.get(k, k): v for k, v in raw.items()}
    data["scenarios"] = [
        s for s in (data.get("scenarios") or []) if isinstance(s, dict)
    ]
    data["themes"] = [t for t in (data.get("themes") or []) if isinstance(t, dict)]
    data["name"] = str(data.get("name") or "").strip()
    for key in ("styleVibe", "alwaysInclude"):
        data[key] = str(data.get(key) or "").strip()
    try:
        return NicheSpec(
            **{k: data.get(k) for k in NicheSpec.model_fields if k in data}
        ).model_dump()
    except ValidationError as exc:
        missing = ", ".join(sorted({str(e["loc"][0]) for e in exc.errors()}))
        raise NicheError(f"Die KI-Nische ist unvollständig ({missing})") from exc


def _extract(parsed) -> list:
    """Akzeptiert {"niches":[...]}, eine nackte Liste oder ein einzelnes Objekt."""
    if isinstance(parsed, dict) and "niches" in parsed:
        parsed = parsed["niches"]
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list) or not parsed:
        raise NicheError("Die KI hat keine Nische geliefert")
    return parsed


def _model(model_id):
    return get_store().get(MODELS, model_id)


def _save(model, spec, source):
    return get_store().create(
        NICHES,
        {
            **spec,
            "modelId": model["id"],
            "market": model.get("market") or "DE",
            "status": "Proposed",
            "source": source,
        },
    )


def generate(model_id, count) -> list:
    if not 1 <= count <= settings.MAX_NICHES_PER_REQUEST:
        raise NicheError(
            f"Zwischen 1 und {settings.MAX_NICHES_PER_REQUEST} Nischen pro Auftrag"
        )
    model = _model(model_id)
    parsed = llm.complete_json(
        prompts.proposals(
            model["name"], model.get("vibe"), count, model.get("language") or "German"
        )
    )
    specs = [validate(raw) for raw in _extract(parsed)][:count]
    return [_save(model, spec, "AI") for spec in specs]


def generate_from_brief(model_id, brief) -> dict:
    brief = (brief or "").strip()
    if len(brief) < 10:
        raise NicheError("Beschreibe die Nische in mindestens einem Satz")
    model = _model(model_id)
    parsed = llm.complete_json(
        prompts.from_brief(model["name"], brief, model.get("language") or "German")
    )
    return _save(model, validate(_extract(parsed)[0]), "Brief")


def propose_improvement(niche_id, hint="") -> dict:
    """Vorschlag für eine überarbeitete Nische. Speichert nichts."""
    niche = get_store().get(NICHES, niche_id)
    model = _model(niche["modelId"])
    parsed = llm.complete_json(
        prompts.improve(
            model["name"],
            niche["name"],
            (hint or "").strip(),
            model.get("language") or "German",
        )
    )
    spec = validate(_extract(parsed)[0])
    spec["name"] = niche["name"]
    return spec
