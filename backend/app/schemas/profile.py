from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.auth import StrictModel, UserSummary


class ConsentStatus(StrictModel):
    media_processing_accepted: bool
    media_processing_accepted_at: datetime | None
    policy_version: str


class ProfileResponse(UserSummary):
    cluster: str | None
    craft_categories: list[str]
    consent: ConsentStatus


class ProfileUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    preferred_language: Literal["hi", "en"] | None = None
    cluster: str | None = Field(default=None, max_length=160)
    craft_categories: list[str] | None = None

    @field_validator("craft_categories")
    @classmethod
    def validate_categories(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("Craft categories cannot contain empty values.")
        if len(cleaned) > 20:
            raise ValueError("At most 20 craft categories are allowed.")
        return list(dict.fromkeys(cleaned))


class MediaConsentRequest(StrictModel):
    accepted: bool
    policy_version: str
