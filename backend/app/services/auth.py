from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from hmac import new as hmac_new
from uuid import uuid4

import jwt
from jwt import InvalidTokenError
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.db.base import ensure_utc
from app.db.models import (
    ApprovalIdempotency,
    BuyerEnquiry,
    CatalogDraft,
    CatalogSnapshot,
    DraftCreateIdempotency,
    EnquiryIdempotency,
    ImageUploadIdempotency,
    MaterialRate,
    MediaObject,
    Operation,
    OperationIdempotency,
    OtpAttempt,
    OtpIdempotency,
    OtpRequest,
    PricingSuggestionIdempotency,
    User,
    VoiceMedia,
    VoiceUploadIdempotency,
)
from app.db.session import Database, get_database
from app.schemas.auth import RequestOtpResponse, UserSummary, VerifyOtpResponse
from app.schemas.profile import ConsentStatus, ProfileResponse, ProfileUpdate


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
    def __init__(self, settings: Settings, database: Database | None = None) -> None:
        self.settings = settings
        self.database = database or get_database()
        self._lock = self.database.write_lock

    def reset(self) -> None:
        """Clear persisted test data in foreign-key-safe order."""
        with self._lock, self.database.session() as session, session.begin():
            session.execute(delete(MaterialRate))
            session.execute(delete(EnquiryIdempotency))
            session.execute(delete(BuyerEnquiry))
            session.execute(delete(ApprovalIdempotency))
            session.execute(delete(CatalogSnapshot))
            session.execute(delete(OperationIdempotency))
            session.execute(delete(Operation))
            session.execute(delete(VoiceUploadIdempotency))
            session.execute(delete(VoiceMedia))
            session.execute(delete(PricingSuggestionIdempotency))
            session.execute(delete(ImageUploadIdempotency))
            session.execute(delete(MediaObject))
            session.execute(delete(DraftCreateIdempotency))
            session.execute(delete(CatalogDraft))
            session.execute(delete(OtpIdempotency))
            session.execute(delete(OtpRequest))
            session.execute(delete(OtpAttempt))
            session.execute(delete(User))

    def request_otp(self, phone: str, idempotency_key: str) -> RequestOtpResponse:
        if self.settings.dev_otp is None:
            raise ApiError(
                503,
                "SERVICE_UNAVAILABLE",
                "OTP delivery is temporarily unavailable.",
            )
        if (
            self.settings.environment == "demo"
            and phone not in self.settings.demo_otp_allowed_phone_e164s
        ):
            raise ApiError(
                403,
                "DEMO_ACCESS_RESTRICTED",
                "This demo is limited to approved phone numbers.",
            )
        now = datetime.now(UTC)
        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    self._lock_phone_for_transaction(session, phone)
                    replay = session.scalar(
                        select(OtpIdempotency).where(
                            OtpIdempotency.phone == phone,
                            OtpIdempotency.idempotency_key == idempotency_key,
                        )
                    )
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        return self._otp_response(replay.request_id)
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    session.execute(
                        delete(OtpRequest).where(
                            OtpRequest.phone == phone,
                            OtpRequest.expires_at <= now,
                        )
                    )

                    if self.settings.environment != "test":
                        window_start = now - timedelta(minutes=15)
                        session.execute(
                            delete(OtpAttempt).where(
                                OtpAttempt.phone == phone,
                                OtpAttempt.created_at < window_start,
                            )
                        )
                        attempt_count = session.scalar(
                            select(func.count(OtpAttempt.id)).where(
                                OtpAttempt.phone == phone,
                                OtpAttempt.created_at >= window_start,
                            )
                        )
                        if (attempt_count or 0) >= self.settings.otp_max_requests_per_15_minutes:
                            raise ApiError(
                                429,
                                "RATE_LIMITED",
                                "Too many OTP requests. Please try again later.",
                                {"retry_after_seconds": 900},
                                {"Retry-After": "900"},
                            )
                        session.add(OtpAttempt(phone=phone, created_at=now))

                    request_id = f"otp_req_{uuid4().hex[:12]}"
                    otp = self.settings.dev_otp
                    session.add(
                        OtpRequest(
                            id=request_id,
                            phone=phone,
                            otp_hash=self._otp_hash(otp),
                            expires_at=now + timedelta(seconds=self.settings.otp_expires_seconds),
                            created_at=now,
                        )
                    )
                    session.add(
                        OtpIdempotency(
                            phone=phone,
                            idempotency_key=idempotency_key,
                            request_id=request_id,
                            expires_at=now
                            + timedelta(seconds=self.settings.otp_idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    return self._otp_response(request_id)
            except IntegrityError:
                return self._replay_after_concurrent_request(phone, idempotency_key, now)

    def verify_otp(self, request_id: str, otp: str) -> VerifyOtpResponse:
        with self._lock, self.database.session() as session, session.begin():
            consumed = session.execute(
                delete(OtpRequest)
                .where(
                    OtpRequest.id == request_id,
                    OtpRequest.expires_at > datetime.now(UTC),
                    OtpRequest.otp_hash == self._otp_hash(otp),
                )
                .returning(OtpRequest.phone)
            ).one_or_none()
            if consumed is None:
                raise ApiError(401, "UNAUTHORIZED", "The OTP is invalid or has expired.")

            phone = consumed[0]
            user = session.scalar(select(User).where(User.phone == phone))
            if user is None:
                user = User(
                    id=f"usr_{uuid4().hex[:12]}",
                    phone=phone,
                    name="Artisan",
                    role="artisan",
                    preferred_language="hi",
                    craft_categories=[],
                    media_processing_accepted=False,
                    policy_version=self.settings.media_consent_policy_version,
                )
                try:
                    with session.begin_nested():
                        session.add(user)
                        session.flush()
                except IntegrityError:
                    user = session.scalar(select(User).where(User.phone == phone))
                    if user is None:
                        raise

            user_record = self._to_record(user)

        now = datetime.now(UTC)
        token = jwt.encode(
            {
                "sub": user_record.id,
                "iat": now,
                "exp": now + timedelta(seconds=self.settings.jwt_expires_seconds),
            },
            self.settings.jwt_secret,
            algorithm=self.settings.jwt_algorithm,
        )
        return VerifyOtpResponse(
            access_token=token,
            token_type="bearer",
            expires_in_seconds=self.settings.jwt_expires_seconds,
            user=self.user_summary(user_record),
        )

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

        with self.database.session() as session:
            user = session.get(User, str(payload["sub"]))
            if user is None:
                raise ApiError(401, "UNAUTHORIZED", "The access token is invalid or expired.")
            return self._to_record(user)

    def profile(self, user: UserRecord) -> ProfileResponse:
        persisted = self._load_user(user.id)
        return ProfileResponse(
            **self.user_summary(persisted).model_dump(),
            cluster=persisted.cluster,
            craft_categories=persisted.craft_categories,
            consent=ConsentStatus(
                media_processing_accepted=persisted.media_processing_accepted,
                media_processing_accepted_at=persisted.media_processing_accepted_at,
                policy_version=persisted.policy_version,
            ),
        )

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

        with self._lock, self.database.session() as session, session.begin():
            persisted = session.get(User, user.id)
            if persisted is None:
                raise ApiError(401, "UNAUTHORIZED", "The access token is invalid or expired.")
            for key, value in values.items():
                setattr(persisted, key, value)
            persisted.updated_at = datetime.now(UTC)
        return self.profile(user)

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
        with self._lock, self.database.session() as session, session.begin():
            persisted = session.get(User, user.id)
            if persisted is None:
                raise ApiError(401, "UNAUTHORIZED", "The access token is invalid or expired.")
            persisted.media_processing_accepted = accepted
            persisted.media_processing_accepted_at = datetime.now(UTC) if accepted else None
            persisted.policy_version = policy_version
            persisted.updated_at = datetime.now(UTC)
        return self.profile(user).consent

    def user_summary(self, user: UserRecord) -> UserSummary:
        return UserSummary(
            id=user.id,
            name=user.name,
            phone=user.phone,
            role=user.role,
            preferred_language=user.preferred_language,
        )

    def _load_user(self, user_id: str) -> UserRecord:
        with self.database.session() as session:
            persisted = session.get(User, user_id)
            if persisted is None:
                raise ApiError(401, "UNAUTHORIZED", "The access token is invalid or expired.")
            return self._to_record(persisted)

    def _replay_after_concurrent_request(
        self, phone: str, idempotency_key: str, now: datetime
    ) -> RequestOtpResponse:
        with self.database.session() as session:
            replay = session.scalar(
                select(OtpIdempotency).where(
                    OtpIdempotency.phone == phone,
                    OtpIdempotency.idempotency_key == idempotency_key,
                )
            )
            if replay is not None and ensure_utc(replay.expires_at) > now:
                return self._otp_response(replay.request_id)
        raise ApiError(409, "IDEMPOTENCY_CONFLICT", "The OTP request could not be replayed.")

    def _otp_response(self, request_id: str) -> RequestOtpResponse:
        return RequestOtpResponse(
            request_id=request_id,
            expires_in_seconds=self.settings.otp_expires_seconds,
            retry_after_seconds=self.settings.otp_retry_after_seconds,
        )

    @staticmethod
    def _lock_phone_for_transaction(session: Session, phone: str) -> None:
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(phone, 0))))

    def _otp_hash(self, otp: str) -> str:
        return hmac_new(
            self.settings.jwt_secret.encode(),
            otp.encode(),
            sha256,
        ).hexdigest()

    def _to_record(self, user: User) -> UserRecord:
        accepted_at = (
            ensure_utc(user.media_processing_accepted_at)
            if user.media_processing_accepted_at is not None
            else None
        )
        return UserRecord(
            id=user.id,
            phone=user.phone,
            name=user.name,
            role=("admin" if self.settings.admin_phone_e164 == user.phone else user.role),
            preferred_language=user.preferred_language,
            cluster=user.cluster,
            craft_categories=list(user.craft_categories),
            media_processing_accepted=user.media_processing_accepted,
            media_processing_accepted_at=accepted_at,
            policy_version=user.policy_version,
        )


@lru_cache
def get_auth_service() -> AuthService:
    return AuthService(get_settings(), get_database())
