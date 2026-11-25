from typing import Literal, Optional

from pydantic import BaseModel, Field

from ..niches.service import Scenario, Theme

Language = Literal["German", "English"]
Market = Literal["DE", "US"]
Nsfw = Literal["sfw", "spicy", "nsfw"]


class ModelIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    vibe: str = Field(default="", max_length=2000)
    language: Language = "German"
    market: Market = "DE"
    notes: str = Field(default="", max_length=4000)


BodyType = Literal["normal", "slim", "curvy", "athletic", "busty"]


class ModelPatch(BaseModel):
    bodyType: Optional[BodyType] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    vibe: Optional[str] = Field(default=None, max_length=2000)
    language: Optional[Language] = None
    market: Optional[Market] = None
    notes: Optional[str] = Field(default=None, max_length=4000)


class GenerateIn(BaseModel):
    count: int = Field(default=3, ge=1, le=6)


class BriefIn(BaseModel):
    brief: str = Field(min_length=10, max_length=4000)


class ImproveIn(BaseModel):
    hint: str = Field(default="", max_length=1000)


class NichePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    styleVibe: Optional[str] = None
    outfits: Optional[list[str]] = Field(default=None, min_length=1, max_length=40)
    backgrounds: Optional[list[str]] = Field(default=None, min_length=1, max_length=40)
    scenarios: Optional[list[Scenario]] = None
    hooks: Optional[list[str]] = None
    themes: Optional[list[Theme]] = None
    alwaysInclude: Optional[str] = None
    dressCode: Optional[Literal["", "authentic"]] = None
    nsfwLevel: Optional[Nsfw] = None
    market: Optional[Market] = None


class StatusIn(BaseModel):
    status: Literal["Proposed", "Approved", "Rejected"]
