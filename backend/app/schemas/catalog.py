from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.auth import StrictModel

DraftStatus = Literal[
    "draft",
    "media_ready",
    "processing",
    "needs_confirmation",
    "ready_for_approval",
    "approved",
    "failed",
]


class ProductFields(StrictModel):
    product_type: str | None = None
    material: str | None = None
    technique: str | None = None
    color: str | None = None
    dimensions: str | None = None
    quantity_available: int | None = Field(default=None, ge=1)
    production_time_days: int | None = Field(default=None, ge=0)
    care: str | None = None
    origin: str | None = None


class ProductFieldsUpdate(StrictModel):
    product_type: str | None = None
    material: str | None = None
    technique: str | None = None
    color: str | None = None
    dimensions: str | None = None
    quantity_available: int | None = Field(default=None, ge=1)
    production_time_days: int | None = Field(default=None, ge=0)
    care: str | None = None
    origin: str | None = None

    @field_validator(
        "product_type",
        "material",
        "technique",
        "color",
        "dimensions",
        "care",
        "origin",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class Listing(StrictModel):
    title_hi: str | None = None
    title_en: str | None = None
    description_hi: str | None = None
    description_en: str | None = None
    tags: list[str] = Field(default_factory=list)


class ListingUpdate(StrictModel):
    title_hi: str | None = None
    title_en: str | None = None
    description_hi: str | None = None
    description_en: str | None = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("title_hi", "title_en", "description_hi", "description_en")
    @classmethod
    def strip_listing_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, value: list[str]) -> list[str]:
        cleaned = [tag.strip() for tag in value]
        if any(not tag for tag in cleaned):
            raise ValueError("Tags cannot contain empty values.")
        return list(dict.fromkeys(cleaned))


class DraftImage(StrictModel):
    id: str
    original_url: str
    enhanced_url: str | None
    is_primary: bool
    selected_variant: Literal["original", "enhanced"] | None
    enhancement_status: Literal["not_started", "queued", "running", "succeeded", "failed"]
    created_at: datetime


class VoiceNote(StrictModel):
    id: str
    language: Literal["hi", "en"]
    status: Literal["uploaded"]
    duration_seconds: int
    created_at: datetime


class Transcript(StrictModel):
    voice_note_id: str
    language: Literal["hi", "en"]
    text: str


class PricingBreakdown(StrictModel):
    material_cost_paise: int
    labour_cost_paise: int
    packaging_cost_paise: int
    logistics_buffer_paise: int
    minimum_sustainable_price_paise: int
    market_reference_low_paise: int
    market_reference_high_paise: int


class PricingSuggestion(StrictModel):
    draft_id: str
    draft_version: int
    suggested_min_paise: int
    suggested_max_paise: int
    recommended_paise: int
    confidence: Literal["low", "medium", "high"]
    breakdown: PricingBreakdown
    reasons: list[str]
    benchmark_category: str
    benchmark_source_label: str
    benchmark_source_date: date
    is_demo_data: bool


class DraftCreate(StrictModel):
    craft_category: str = Field(min_length=1, max_length=120)
    source_language: Literal["hi", "en"]
    initial_notes: str | None = Field(default=None, max_length=1000)

    @field_validator("craft_category")
    @classmethod
    def clean_category(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Craft category cannot be blank.")
        return cleaned

    @field_validator("initial_notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class DraftPatch(StrictModel):
    version: int = Field(ge=1)
    fields: ProductFieldsUpdate | None = None
    listing: ListingUpdate | None = None

    @model_validator(mode="after")
    def require_change(self) -> "DraftPatch":
        has_field_change = self.fields is not None and bool(self.fields.model_fields_set)
        has_listing_change = self.listing is not None and bool(self.listing.model_fields_set)
        if not has_field_change and not has_listing_change:
            raise ValueError("At least one of fields or listing must be supplied.")
        return self


class Draft(StrictModel):
    id: str
    version: int
    status: DraftStatus
    craft_category: str
    source_language: Literal["hi", "en"]
    initial_notes: str | None
    fields: ProductFields
    listing: Listing | None
    images: list[DraftImage]
    voice_notes: list[VoiceNote]
    transcript: Transcript | None
    field_confidence: dict[str, float]
    missing_fields: list[str]
    pricing: PricingSuggestion | None
    last_processing_error: dict[str, object] | None
    created_at: datetime
    updated_at: datetime


class DraftSummary(StrictModel):
    id: str
    version: int
    status: DraftStatus
    title_hi: str | None
    title_en: str | None
    thumbnail_url: str | None
    recommended_price_paise: int | None
    updated_at: datetime


class DraftList(StrictModel):
    items: list[DraftSummary]
    next_cursor: str | None
