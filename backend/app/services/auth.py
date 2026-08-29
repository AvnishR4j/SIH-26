from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from threading import RLock
from time import monotonic
from uuid import uuid4

import jwt
from jwt import InvalidTokenError

from app.core.concurrency import synchronized
from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.schemas.auth import RequestOtpResponse, UserSummary, VerifyOtpResponse
from app.schemas.profile import ConsentStatus, ProfileResponse, ProfileUpdate


@dataclass
class OtpRecord:
    request_id: str
    phone: str
    otp: str
    expires_at: float


@dataclass
class IdempotencyRecord:
    response: RequestOtpResponse
    expires_at: float


@dataclass
class UserRecord:
    id: str
    phone: str
    name: str = "Artisan"
    role: str = "artisan"
    preferred_language: str = "hi"
    cluster: str | None = None
    craft_categories: list[str] = field(default_factory=list)
    media_processing_accepted: bool = False
    media_processing_accepted_at: datetime | None = None
    policy_version: str = "2026-08-29"


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.otp_requests: dict[str, OtpRecord] = {}
        self.otp_idempotency: dict[tuple[str, str], IdempotencyRecord] = {}
        self.otp_attempts: dict[str, list[float]] = {}
        self.users_by_id: dict[str, UserRecord] = {}
        self.user_ids_by_phone: dict[str, str] = {}
        self._lock = RLock()

    @synchronized
    def reset(self) -> None:
        self.otp_requests.clear()
        self.otp_idempotency.clear()
        self.otp_attempts.clear()
        self.users_by_id.clear()
        self.user_ids_by_phone.clear()

    @synchronized
    def request_otp(self, phone: str, idempotency_key: str) -> RequestOtpResponse:
        now = monotonic()
        scope = (phone, idempotency_key)
        replay = self.otp_idempotency.get(scope)
        if replay and replay.expires_at > now:
            return replay.response

        if self.settings.environment != "test":
            window_start = now - 900
            attempts = [value for value in self.otp_attempts.get(phone, []) if value > window_start]
            if len(attempts) >= self.settings.otp_max_requests_per_15_minutes:
                raise ApiError(
                    429,
                    "RATE_LIMITED",
                    "Too many OTP requests. Please try again later.",
                    {"retry_after_seconds": 900},
                    {"Retry-After": "900"},
                )
            attempts.append(now)
            self.otp_attempts[phone] = attempts

        request_id = f"otp_req_{uuid4().hex[:12]}"
        otp = self.settings.dev_otp or f"{int(uuid4().hex[:8], 16) % 1_000_000:06d}"
        response = RequestOtpResponse(
            request_id=request_id,
            expires_in_seconds=self.settings.otp_expires_seconds,
            retry_after_seconds=self.settings.otp_retry_after_seconds,
        )
        self.otp_requests[request_id] = OtpRecord(
            request_id=request_id,
            phone=phone,
            otp=otp,
            expires_at=now + self.settings.otp_expires_seconds,
        )
        self.otp_idempotency[scope] = IdempotencyRecord(
            response=response,
            expires_at=now + self.settings.otp_idempotency_ttl_seconds,
        )
        return response

    @synchronized
    def verify_otp(self, request_id: str, otp: str) -> VerifyOtpResponse:
        record = self.otp_requests.get(request_id)
        if record is None or record.expires_at <= monotonic() or record.otp != otp:
            raise ApiError(401, "UNAUTHORIZED", "The OTP is invalid or has expired.")

        user = self._get_or_create_user(record.phone)
        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": user.id,
                "iat": now,
                "exp": now + timedelta(seconds=self.settings.jwt_expires_seconds),
            },
            self.settings.jwt_secret,
            algorithm=self.settings.jwt_algorithm,
        )
        del self.otp_requests[request_id]
        return VerifyOtpResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=self.settings.jwt_expires_seconds,
            user=self.user_summary(user),
        )

    @synchronized
    def authenticate(self, token: str) -> UserRecord:
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
                options={"require": ["sub", "exp"]},
            )
        except InvalidTokenError as error:
            raise ApiError(
                401, "UNAUTHORIZED", "The access token is invalid or expired."
            ) from error
        user = self.users_by_id.get(str(payload["sub"]))
        if user is None:
            raise ApiError(401, "UNAUTHORIZED", "The access token is invalid or expired.")
        return user

    @synchronized
    def profile(self, user: UserRecord) -> ProfileResponse:
        return ProfileResponse(
            **self.user_summary(user).model_dump(),
            cluster=user.cluster,
            craft_categories=user.craft_categories,
            consent=ConsentStatus(
                media_processing_accepted=user.media_processing_accepted,
                media_processing_accepted_at=user.media_processing_accepted_at,
                policy_version=user.policy_version,
            ),
        )

    @synchronized
    def update_profile(self, user: UserRecord, update: ProfileUpdate) -> ProfileResponse:
        values = update.model_dump(exclude_unset=True)
        for required_field in ("name", "preferred_language", "craft_categories"):
            if required_field in values and values[required_field] is None:
                raise ApiError(
                    422,
                    "VALIDATION_ERROR",
                    "Some fields need attention.",
                    {"fields": {required_field: "This field cannot be null."}},
                )
        for key, value in values.items():
            setattr(user, key, value)
        return self.profile(user)

    @synchronized
    def update_consent(
        self, user: UserRecord, accepted: bool, policy_version: str
    ) -> ConsentStatus:
        if policy_version != self.settings.media_consent_policy_version:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "The consent policy has changed. Please review the current version.",
                {"fields": {"policy_version": self.settings.media_consent_policy_version}},
            )
        user.media_processing_accepted = accepted
        user.media_processing_accepted_at = datetime.now(UTC) if accepted else None
        user.policy_version = policy_version
        return self.profile(user).consent

    def user_summary(self, user: UserRecord) -> UserSummary:
        return UserSummary(
            id=user.id,
            name=user.name,
            phone=user.phone,
            role=user.role,
            preferred_language=user.preferred_language,
        )

    def _get_or_create_user(self, phone: str) -> UserRecord:
        existing_id = self.user_ids_by_phone.get(phone)
        if existing_id:
            return self.users_by_id[existing_id]
        user = UserRecord(
            id=f"usr_{uuid4().hex[:12]}",
            phone=phone,
            policy_version=self.settings.media_consent_policy_version,
        )
        self.users_by_id[user.id] = user
        self.user_ids_by_phone[phone] = user.id
        return user


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(get_settings())
