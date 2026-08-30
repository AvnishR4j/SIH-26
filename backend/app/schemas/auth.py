import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

PHONE_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestOtpRequest(StrictModel):
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        normalized = value.strip()
        if not PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Use an E.164 phone number such as +919999999999.")
        return normalized


class RequestOtpResponse(StrictModel):
    request_id: str
    expires_in_seconds: int
    retry_after_seconds: int


class VerifyOtpRequest(StrictModel):
    request_id: str
    otp: str

    @field_validator("otp")
    @classmethod
    def validate_otp(cls, value: str) -> str:
        if not re.fullmatch(r"\d{6}", value):
            raise ValueError("OTP must contain exactly 6 digits.")
        return value


class UserSummary(StrictModel):
    id: str
    name: str
    phone: str
    role: Literal["artisan", "facilitator", "admin"]
    preferred_language: Literal["hi", "en"]


class VerifyOtpResponse(StrictModel):
    access_token: str
    token_type: Literal["bearer"]
    expires_in_seconds: int
    user: UserSummary
