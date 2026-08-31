from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, ClassVar, Literal, Protocol

from google import genai
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.schemas.catalog import Draft, Listing, ProductFields


class CatalogueGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: ProductFields
    listing: Listing
    field_confidence: dict[str, float]


class CatalogueGenerator(Protocol):
    def generate(
        self,
        draft: Draft,
        transcript: str,
        source_language: Literal["hi", "en"],
        target_languages: list[Literal["hi", "en"]],
    ) -> CatalogueGenerationResult: ...


class GroundedText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str = Field(min_length=1, max_length=240)
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("value", "evidence")
    @classmethod
    def strip_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Text cannot be blank.")
        return cleaned


class GroundedInteger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: int
    evidence: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)

    @field_validator("evidence")
    @classmethod
    def strip_evidence(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Evidence cannot be blank.")
        return cleaned


class GeneratedListing(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title_hi: str | None = Field(default=None, max_length=160)
    title_en: str | None = Field(default=None, max_length=160)
    description_hi: str | None = Field(default=None, max_length=1200)
    description_en: str | None = Field(default=None, max_length=1200)
    source_evidence: list[str] = Field(min_length=1, max_length=8)

    @field_validator("title_hi", "title_en", "description_hi", "description_en")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("source_evidence")
    @classmethod
    def clean_evidence(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("Listing evidence cannot contain blank values.")
        return list(dict.fromkeys(cleaned))


class GeminiCatalogueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_type: GroundedText | None = None
    material: GroundedText | None = None
    technique: GroundedText | None = None
    color: GroundedText | None = None
    dimensions: GroundedText | None = None
    quantity_available: GroundedInteger | None = None
    production_time_days: GroundedInteger | None = None
    care: GroundedText | None = None
    origin: GroundedText | None = None
    listing: GeneratedListing


class MockCatalogueGenerator:
    def generate(
        self,
        draft: Draft,
        transcript: str,
        source_language: Literal["hi", "en"],
        target_languages: list[Literal["hi", "en"]],
    ) -> CatalogueGenerationResult:
        existing = draft.listing or Listing(
            title_hi=None,
            title_en=None,
            description_hi=None,
            description_en=None,
            tags=[],
        )
        title_hi = existing.title_hi
        title_en = existing.title_en
        description_hi = existing.description_hi
        description_en = existing.description_en
        if "hi" in target_languages:
            title_hi = title_hi or draft.craft_category
            if source_language == "hi":
                description_hi = description_hi or transcript
        if "en" in target_languages:
            title_en = title_en or draft.craft_category
            if source_language == "en":
                description_en = description_en or transcript
        return CatalogueGenerationResult(
            fields=draft.fields,
            listing=Listing(
                title_hi=title_hi,
                title_en=title_en,
                description_hi=description_hi,
                description_en=description_en,
                tags=existing.tags or [draft.craft_category],
            ),
            field_confidence=draft.field_confidence,
        )


class GeminiCatalogueGenerator:
    _SENSITIVE_CONTACT_PATTERN: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:\+?\d[\d\s().-]{7,}\d)|(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})|(?:https?://|www\.)",
        re.IGNORECASE,
    )
    _TEXT_FIELDS = (
        "product_type",
        "material",
        "technique",
        "color",
        "dimensions",
        "care",
        "origin",
    )
    _INTEGER_LIMITS: ClassVar[dict[str, tuple[int, int]]] = {
        "quantity_available": (1, 1_000_000),
        "production_time_days": (0, 3_650),
    }

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        if settings.gemini_api_key is None:
            raise ValueError("Gemini API key is required.")
        self.client = client or genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=settings.ai_provider_timeout_seconds * 1000),
        )

    def generate(
        self,
        draft: Draft,
        transcript: str,
        source_language: Literal["hi", "en"],
        target_languages: list[Literal["hi", "en"]],
    ) -> CatalogueGenerationResult:
        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model,
                contents=self._prompt(draft, transcript, source_language, target_languages),
                config=types.GenerateContentConfig(
                    system_instruction=self._system_instruction(),
                    response_mime_type="application/json",
                    response_schema=GeminiCatalogueResponse,
                    max_output_tokens=2500,
                ),
            )
            parsed = response.parsed
            if isinstance(parsed, GeminiCatalogueResponse):
                generated = parsed
            elif parsed is not None:
                generated = GeminiCatalogueResponse.model_validate(parsed)
            else:
                generated = GeminiCatalogueResponse.model_validate_json(response.text)
        except Exception as error:
            raise ApiError(
                503,
                "AI_SERVICE_UNAVAILABLE",
                "Catalogue generation is temporarily unavailable.",
            ) from error
        return self._ground_and_merge(draft, transcript, target_languages, generated)

    @staticmethod
    def _system_instruction() -> str:
        return (
            "You extract artisan product facts and draft marketplace copy. "
            "Never invent a product fact. Return null for every unknown field. "
            "Every extracted field must include a verbatim evidence span copied from the "
            "transcript. Listing source_evidence must contain only verbatim transcript spans. "
            "Do not infer prices, costs, phone numbers, addresses, or personal data. "
            "Write concise catalogue copy only in the requested target languages."
        )

    @staticmethod
    def _prompt(
        draft: Draft,
        transcript: str,
        source_language: str,
        target_languages: list[str],
    ) -> str:
        confirmed = {
            name: value
            for name, value in draft.fields.model_dump(mode="json").items()
            if value is not None
        }
        return json.dumps(
            {
                "task": "Extract grounded product fields and draft bilingual catalogue copy.",
                "craft_category": draft.craft_category,
                "source_language": source_language,
                "target_languages": target_languages,
                "artisan_confirmed_fields": confirmed,
                "transcript": transcript,
            },
            ensure_ascii=False,
        )

    def _ground_and_merge(
        self,
        draft: Draft,
        transcript: str,
        target_languages: list[str],
        generated: GeminiCatalogueResponse,
    ) -> CatalogueGenerationResult:
        field_updates: dict[str, object] = {}
        confidence = dict(draft.field_confidence)
        for name in self._TEXT_FIELDS:
            if getattr(draft.fields, name) is not None:
                continue
            candidate = getattr(generated, name)
            if (
                candidate is not None
                and not self._contains_sensitive_contact(candidate.value)
                and self._is_verbatim(candidate.evidence, transcript)
            ):
                field_updates[name] = candidate.value
                confidence[name] = candidate.confidence
        for name, (minimum, maximum) in self._INTEGER_LIMITS.items():
            if getattr(draft.fields, name) is not None:
                continue
            candidate = getattr(generated, name)
            if (
                candidate is not None
                and minimum <= candidate.value <= maximum
                and self._is_verbatim(candidate.evidence, transcript)
            ):
                field_updates[name] = candidate.value
                confidence[name] = candidate.confidence

        fields = draft.fields.model_copy(update=field_updates)
        listing = self._merge_listing(
            draft, fields, transcript, target_languages, generated.listing
        )
        return CatalogueGenerationResult(
            fields=fields,
            listing=listing,
            field_confidence=confidence,
        )

    def _merge_listing(
        self,
        draft: Draft,
        fields: ProductFields,
        transcript: str,
        target_languages: list[str],
        generated: GeneratedListing,
    ) -> Listing:
        existing = draft.listing or Listing(
            title_hi=None,
            title_en=None,
            description_hi=None,
            description_en=None,
            tags=[],
        )
        listing_is_grounded = all(
            self._is_verbatim(evidence, transcript) for evidence in generated.source_evidence
        ) and not any(
            self._contains_sensitive_contact(value)
            for value in (
                generated.title_hi,
                generated.title_en,
                generated.description_hi,
                generated.description_en,
            )
            if value is not None
        )
        values: dict[str, str | None] = {
            "title_hi": existing.title_hi,
            "title_en": existing.title_en,
            "description_hi": existing.description_hi,
            "description_en": existing.description_en,
        }
        if listing_is_grounded:
            for language in target_languages:
                for prefix in ("title", "description"):
                    name = f"{prefix}_{language}"
                    values[name] = values[name] or getattr(generated, name)

        tags = existing.tags or self._grounded_tags(draft.craft_category, fields)
        return Listing(**values, tags=tags)

    @staticmethod
    def _grounded_tags(craft_category: str, fields: ProductFields) -> list[str]:
        candidates = [
            craft_category,
            fields.product_type,
            fields.material,
            fields.technique,
            fields.origin,
        ]
        return list(dict.fromkeys(value.strip() for value in candidates if value and value.strip()))

    @staticmethod
    def _is_verbatim(evidence: str, transcript: str) -> bool:
        normalize = lambda value: re.sub(r"\s+", " ", value).strip().casefold()
        normalized_evidence = normalize(evidence)
        return bool(normalized_evidence) and normalized_evidence in normalize(transcript)

    @classmethod
    def _contains_sensitive_contact(cls, value: str) -> bool:
        return cls._SENSITIVE_CONTACT_PATTERN.search(value) is not None


@lru_cache
def get_catalogue_generator() -> CatalogueGenerator:
    settings = get_settings()
    if settings.catalogue_generation_provider == "gemini":
        return GeminiCatalogueGenerator(settings)
    return MockCatalogueGenerator()
