import re
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.schemas.auth import PHONE_PATTERN, StrictModel


class ApprovalRequest(StrictModel):
    version: int = Field(ge=1)
    approved_price_paise: int = Field(gt=0)
    price_override_reason: str | None = Field(default=None, max_length=500)
    approval_note: str | None = Field(default=None, max_length=1000)

    @field_validator("price_override_reason", "approval_note")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ApprovedCatalog(StrictModel):
    id: str
    draft_id: str
    status: Literal["approved"]
    approved_price_paise: int = Field(gt=0)
    currency: Literal["INR"]
    public_share_id: str
    public_share_url: str
    created_at: datetime


class PublicArtisan(StrictModel):
    display_name: str
    cluster: str | None


class PublicShareCard(StrictModel):
    catalog_id: str
    title: str
    description: str
    image_url: str
    price_paise: int = Field(gt=0)
    currency: Literal["INR"]
    quantity_available: int = Field(ge=1)
    artisan: PublicArtisan
    enquiry_enabled: bool
    published_at: datetime


class MarketplaceCatalogue(StrictModel):
    public_share_id: str
    title: str
    description: str
    image_url: str
    price_paise: int = Field(gt=0)
    currency: Literal["INR"]
    quantity_available: int = Field(ge=1)
    artisan: PublicArtisan
    published_at: datetime


class MarketplaceCataloguePage(StrictModel):
    items: list[MarketplaceCatalogue]
    next_cursor: str | None


class EnquiryRequest(StrictModel):
    buyer_name: str = Field(min_length=1, max_length=120)
    buyer_phone: str
    message: str | None = Field(default=None, max_length=1000)
    quantity_requested: int | None = Field(default=None, ge=1)
    consent_to_contact: Literal[True]

    @field_validator("buyer_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value.strip())
        if not cleaned:
            raise ValueError("Buyer name cannot be blank.")
        return cleaned

    @field_validator("buyer_phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Use an E.164 phone number such as +919999999999.")
        return normalized

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class EnquiryResponse(StrictModel):
    enquiry_id: str
    status: Literal["received"]
    received_at: datetime
