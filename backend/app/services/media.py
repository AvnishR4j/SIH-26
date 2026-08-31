from __future__ import annotations

import warnings
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.db.base import ensure_utc
from app.db.models import (
    CatalogDraft,
    ImageUploadIdempotency,
    MediaObject,
    Operation,
    OperationIdempotency,
)
from app.db.session import Database, get_database
from app.schemas.catalog import (
    Draft,
    DraftImage,
    DraftImagePatch,
    ImageEnhancementRequest,
)
from app.schemas.operations import OperationResponse
from app.services.auth import UserRecord
from app.services.media_urls import refresh_draft_image_urls, refresh_image_urls
from app.storage.base import MediaStorage
from app.storage.factory import create_media_storage, get_media_storage

IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


class MediaService:
    def __init__(
        self,
        settings: Settings,
        database: Database | None = None,
        storage: MediaStorage | None = None,
    ) -> None:
        self.settings = settings
        self.database = database or get_database()
        self.storage = storage or create_media_storage(settings)
        self._lock = self.database.write_lock

    def upload_image(
        self,
        user: UserRecord,
        draft_id: str,
        content: bytes,
        is_primary: bool,
        idempotency_key: str,
    ) -> DraftImage:
        content_type, extension = self._validate_image(content)
        request_hash = sha256(
            content + b"\0is_primary=" + (b"true" if is_primary else b"false")
        ).hexdigest()
        now = datetime.now(UTC)
        saved_key: str | None = None

        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = self._image_replay(session, user.id, idempotency_key)
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        if replay.request_hash != request_hash:
                            raise self._idempotency_conflict()
                        image = DraftImage.model_validate(replay.response_payload)
                        media = session.get(MediaObject, image.id)
                        return refresh_image_urls(image, media, self.storage)
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    row = self._owned_draft_row(session, user.id, draft_id, lock=True)
                    draft = Draft.model_validate(row.payload)
                    self._ensure_editable(draft)

                    image_id = f"img_{uuid4().hex[:12]}"
                    saved_key = f"drafts/{user.id}/{draft.id}/{image_id}/original.{extension}"
                    self.storage.save(saved_key, content)
                    make_primary = not draft.images or is_primary
                    images = [
                        existing.model_copy(update={"is_primary": False})
                        if make_primary and existing.is_primary
                        else existing
                        for existing in draft.images
                    ]
                    image = DraftImage(
                        id=image_id,
                        original_url=self.storage.url(saved_key),
                        enhanced_url=None,
                        is_primary=make_primary,
                        selected_variant=None,
                        enhancement_status="not_started",
                        created_at=now,
                    )
                    images.append(image)
                    status = (
                        "media_ready"
                        if draft.status == "draft" and draft.voice_notes
                        else draft.status
                    )
                    updated = draft.model_copy(
                        update={"images": images, "status": status, "updated_at": now}
                    )
                    row.status = updated.status
                    row.payload = updated.model_dump(mode="json")
                    row.updated_at = now
                    session.add(
                        MediaObject(
                            id=image.id,
                            owner_id=user.id,
                            draft_id=draft.id,
                            original_key=saved_key,
                            original_content_type=content_type,
                            original_size_bytes=len(content),
                            original_sha256=sha256(content).hexdigest(),
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    session.flush()
                    session.add(
                        ImageUploadIdempotency(
                            owner_id=user.id,
                            idempotency_key=idempotency_key,
                            request_hash=request_hash,
                            response_payload=image.model_dump(mode="json"),
                            image_id=image.id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    return image
            except IntegrityError:
                if saved_key is not None:
                    self.storage.delete(saved_key)
                return self._replay_image_after_race(user.id, idempotency_key, request_hash, now)
            except Exception:
                if saved_key is not None:
                    self.storage.delete(saved_key)
                raise

    def start_image_enhancement(
        self,
        user: UserRecord,
        draft_id: str,
        image_id: str,
        request: ImageEnhancementRequest,
        idempotency_key: str,
    ) -> tuple[OperationResponse, bool]:
        self._require_current_consent(user)
        now = datetime.now(UTC)
        request_payload = {
            "draft_id": draft_id,
            "image_id": image_id,
            **request.model_dump(mode="json"),
        }
        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = self._operation_replay(
                        session, user.id, "enhance_image", idempotency_key
                    )
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        if replay.request_payload != request_payload:
                            raise self._idempotency_conflict()
                        response = OperationResponse.model_validate(replay.response_payload)
                        operation = session.get(Operation, replay.operation_id)
                        should_schedule = operation is not None and operation.status == "queued"
                        return response, should_schedule
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    row = self._owned_draft_row(session, user.id, draft_id, lock=True)
                    draft = Draft.model_validate(row.payload)
                    concurrent_replay = self._operation_replay(
                        session, user.id, "enhance_image", idempotency_key
                    )
                    if (
                        concurrent_replay is not None
                        and ensure_utc(concurrent_replay.expires_at) > now
                    ):
                        if concurrent_replay.request_payload != request_payload:
                            raise self._idempotency_conflict()
                        response = OperationResponse.model_validate(
                            concurrent_replay.response_payload
                        )
                        operation = session.get(Operation, concurrent_replay.operation_id)
                        return response, (operation is not None and operation.status == "queued")
                    self._ensure_editable(draft)
                    image = self._find_image(draft, image_id)
                    if image.enhancement_status in {"queued", "running"}:
                        raise ApiError(
                            409,
                            "INVALID_STATE",
                            "Image enhancement is already in progress.",
                        )
                    media = session.scalar(
                        select(MediaObject).where(
                            MediaObject.id == image_id,
                            MediaObject.owner_id == user.id,
                            MediaObject.draft_id == draft_id,
                        )
                    )
                    if media is None:
                        raise ApiError(404, "NOT_FOUND", "The image was not found.")

                    operation_id = f"op_{uuid4().hex[:12]}"
                    response = OperationResponse(
                        id=operation_id,
                        type="enhance_image",
                        status="queued",
                        resource_type="draft",
                        resource_id=draft.id,
                        poll_after_seconds=self.settings.ai_operation_poll_after_seconds,
                        error=None,
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(
                        Operation(
                            id=operation_id,
                            owner_id=user.id,
                            type="enhance_image",
                            status="queued",
                            resource_type="draft",
                            resource_id=draft.id,
                            internal_payload=request_payload,
                            error=None,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    session.flush()
                    session.add(
                        OperationIdempotency(
                            owner_id=user.id,
                            operation_type="enhance_image",
                            idempotency_key=idempotency_key,
                            request_payload=request_payload,
                            response_payload=response.model_dump(mode="json"),
                            operation_id=operation_id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    updated_images = [
                        existing.model_copy(update={"enhancement_status": "queued"})
                        if existing.id == image_id
                        else existing
                        for existing in draft.images
                    ]
                    updated = draft.model_copy(
                        update={
                            "images": updated_images,
                            "last_processing_error": None,
                            "updated_at": now,
                        }
                    )
                    row.payload = updated.model_dump(mode="json")
                    row.updated_at = now
                    return response, True
            except IntegrityError:
                return self._replay_operation_after_race(
                    user.id,
                    "enhance_image",
                    idempotency_key,
                    request_payload,
                    now,
                )

    def complete_image_enhancement(self, owner_id: str, operation_id: str) -> None:
        enhanced_key: str | None = None
        try:
            with self._lock, self.database.session() as session, session.begin():
                operation = session.scalar(
                    select(Operation)
                    .where(Operation.id == operation_id, Operation.owner_id == owner_id)
                    .with_for_update()
                )
                if operation is None or operation.status != "queued":
                    return
                operation.status = "running"
                operation.updated_at = datetime.now(UTC)
                payload = dict(operation.internal_payload)
                media = session.scalar(
                    select(MediaObject).where(
                        MediaObject.id == payload["image_id"],
                        MediaObject.owner_id == owner_id,
                    )
                )
                if media is None:
                    raise ApiError(404, "NOT_FOUND", "The image was not found.")
                original_key = media.original_key

            enhanced = self._enhance_image(
                self.storage.read(original_key),
                background=str(payload["background"]),
                crop_style=str(payload["crop_style"]),
            )
            enhanced_key = (
                f"drafts/{owner_id}/{payload['draft_id']}/{payload['image_id']}/enhanced.jpg"
            )
            self.storage.save(enhanced_key, enhanced)
            now = datetime.now(UTC)

            with self._lock, self.database.session() as session, session.begin():
                operation = session.get(Operation, operation_id)
                media = session.get(MediaObject, str(payload["image_id"]))
                row = self._owned_draft_row(session, owner_id, str(payload["draft_id"]), lock=True)
                if operation is None or media is None:
                    raise ApiError(404, "NOT_FOUND", "The enhancement operation was not found.")
                draft = Draft.model_validate(row.payload)
                enhanced_url = self.storage.url(enhanced_key)
                images = [
                    image.model_copy(
                        update={
                            "enhanced_url": enhanced_url,
                            "enhancement_status": "succeeded",
                        }
                    )
                    if image.id == payload["image_id"]
                    else image
                    for image in draft.images
                ]
                updated = draft.model_copy(
                    update={
                        "images": images,
                        "last_processing_error": None,
                        "updated_at": now,
                    }
                )
                row.payload = updated.model_dump(mode="json")
                row.updated_at = now
                media.enhanced_key = enhanced_key
                media.enhanced_content_type = "image/jpeg"
                media.enhanced_size_bytes = len(enhanced)
                media.enhanced_sha256 = sha256(enhanced).hexdigest()
                media.updated_at = now
                operation.status = "succeeded"
                operation.error = None
                operation.updated_at = now
        # Background jobs must persist an actionable failure instead of escaping silently.
        except Exception as error:  # noqa: BLE001
            if enhanced_key is not None:
                self.storage.delete(enhanced_key)
            self._record_operation_failure(owner_id, operation_id, error)

    def update_image(
        self,
        user: UserRecord,
        draft_id: str,
        image_id: str,
        request: DraftImagePatch,
    ) -> Draft:
        with self._lock, self.database.session() as session, session.begin():
            row = self._owned_draft_row(session, user.id, draft_id, lock=True)
            draft = Draft.model_validate(row.payload)
            self._ensure_editable(draft)
            if request.version != draft.version:
                raise self._version_conflict(draft.version)
            target = self._find_image(draft, image_id)
            if request.is_primary is False and target.is_primary:
                raise ApiError(
                    400,
                    "INVALID_STATE",
                    "The primary image cannot be unset without promoting a replacement.",
                )
            if request.selected_variant == "enhanced" and (
                target.enhancement_status != "succeeded" or target.enhanced_url is None
            ):
                raise ApiError(
                    400,
                    "INVALID_STATE",
                    "The enhanced image is not ready for selection.",
                )

            images: list[DraftImage] = []
            for image in draft.images:
                changes: dict[str, object] = {}
                if request.is_primary is True:
                    changes["is_primary"] = image.id == image_id
                if image.id == image_id and request.selected_variant is not None:
                    changes["selected_variant"] = request.selected_variant
                images.append(image.model_copy(update=changes) if changes else image)

            now = datetime.now(UTC)
            updated = draft.model_copy(
                update={
                    "images": images,
                    "version": draft.version + 1,
                    "updated_at": now,
                }
            )
            result = session.execute(
                update(CatalogDraft)
                .where(
                    CatalogDraft.id == draft_id,
                    CatalogDraft.owner_id == user.id,
                    CatalogDraft.version == request.version,
                )
                .values(
                    version=updated.version,
                    status=updated.status,
                    payload=updated.model_dump(mode="json"),
                    updated_at=now,
                )
            )
            if result.rowcount != 1:
                current = session.scalar(
                    select(CatalogDraft.version).where(
                        CatalogDraft.id == draft_id,
                        CatalogDraft.owner_id == user.id,
                    )
                )
                if current is None:
                    raise ApiError(404, "NOT_FOUND", "The draft was not found.")
                raise self._version_conflict(current)
            return refresh_draft_image_urls(session, updated, self.storage)

    def get_operation(self, user: UserRecord, operation_id: str) -> OperationResponse:
        with self.database.session() as session:
            operation = session.scalar(
                select(Operation).where(
                    Operation.id == operation_id,
                    Operation.owner_id == user.id,
                )
            )
            if operation is None:
                raise ApiError(404, "NOT_FOUND", "The operation was not found.")
            return self._operation_response(operation)

    def _record_operation_failure(self, owner_id: str, operation_id: str, error: Exception) -> None:
        if isinstance(error, ApiError):
            failure = {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            }
        else:
            failure = {
                "code": "INTERNAL_ERROR",
                "message": "Image enhancement failed.",
                "details": {},
            }
        now = datetime.now(UTC)
        with self._lock, self.database.session() as session, session.begin():
            operation = session.scalar(
                select(Operation).where(
                    Operation.id == operation_id,
                    Operation.owner_id == owner_id,
                )
            )
            if operation is None:
                return
            operation.status = "failed"
            operation.error = failure
            operation.updated_at = now
            row = session.get(CatalogDraft, operation.resource_id)
            if row is None:
                return
            draft = Draft.model_validate(row.payload)
            image_id = operation.internal_payload.get("image_id")
            images = [
                image.model_copy(update={"enhancement_status": "failed"})
                if image.id == image_id
                else image
                for image in draft.images
            ]
            updated = draft.model_copy(
                update={
                    "images": images,
                    "last_processing_error": failure,
                    "updated_at": now,
                }
            )
            row.payload = updated.model_dump(mode="json")
            row.updated_at = now

    def _validate_image(self, content: bytes) -> tuple[str, str]:
        if not content:
            raise ApiError(422, "VALIDATION_ERROR", "The image file is empty.")
        if len(content) > self.settings.max_image_bytes:
            raise ApiError(
                413,
                "UPLOAD_TOO_LARGE",
                "The image exceeds the 10 MB upload limit.",
                {"max_bytes": self.settings.max_image_bytes},
            )
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    image_format = image.format
                    if image.width * image.height > self.settings.max_image_pixels:
                        raise ApiError(
                            413,
                            "UPLOAD_TOO_LARGE",
                            "The decoded image dimensions are too large.",
                            {"max_pixels": self.settings.max_image_pixels},
                        )
                    if getattr(image, "is_animated", False):
                        raise ApiError(
                            415,
                            "UNSUPPORTED_MEDIA_TYPE",
                            "Animated images are not supported.",
                        )
                    image.verify()
        except ApiError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            SyntaxError,
        ) as error:
            raise ApiError(
                415,
                "UNSUPPORTED_MEDIA_TYPE",
                "Upload a valid JPEG, PNG, or WebP image.",
            ) from error
        if image_format not in IMAGE_FORMATS:
            raise ApiError(
                415,
                "UNSUPPORTED_MEDIA_TYPE",
                "Upload a valid JPEG, PNG, or WebP image.",
            )
        return IMAGE_FORMATS[image_format]

    @staticmethod
    def _enhance_image(content: bytes, background: str, crop_style: str) -> bytes:
        with Image.open(BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        if crop_style == "marketplace_square":
            side = max(image.size)
            fill = (245, 245, 245) if background == "neutral" else (255, 255, 255)
            image = ImageOps.pad(image, (side, side), method=Image.Resampling.LANCZOS, color=fill)
        image = ImageOps.autocontrast(image, cutoff=1)
        image = ImageEnhance.Contrast(image).enhance(1.05)
        image = ImageEnhance.Sharpness(image).enhance(1.1)
        output = BytesIO()
        image.save(output, format="JPEG", quality=90, optimize=True)
        return output.getvalue()

    def _require_current_consent(self, user: UserRecord) -> None:
        if not user.media_processing_accepted or (
            user.policy_version != self.settings.media_consent_policy_version
        ):
            raise ApiError(
                403,
                "CONSENT_REQUIRED",
                "Accept the current media-processing policy before using AI features.",
                {"policy_version": self.settings.media_consent_policy_version},
            )

    @staticmethod
    def _ensure_editable(draft: Draft) -> None:
        if draft.status == "approved":
            raise ApiError(400, "INVALID_STATE", "An approved draft cannot be changed.")

    @staticmethod
    def _find_image(draft: Draft, image_id: str) -> DraftImage:
        image = next((item for item in draft.images if item.id == image_id), None)
        if image is None:
            raise ApiError(404, "NOT_FOUND", "The image was not found.")
        return image

    @staticmethod
    def _owned_draft_row(
        session: Session, owner_id: str, draft_id: str, *, lock: bool
    ) -> CatalogDraft:
        statement = select(CatalogDraft).where(
            CatalogDraft.id == draft_id,
            CatalogDraft.owner_id == owner_id,
        )
        if lock:
            statement = statement.with_for_update()
        row = session.scalar(statement)
        if row is None:
            raise ApiError(404, "NOT_FOUND", "The draft was not found.")
        return row

    @staticmethod
    def _image_replay(
        session: Session, owner_id: str, idempotency_key: str
    ) -> ImageUploadIdempotency | None:
        return session.scalar(
            select(ImageUploadIdempotency).where(
                ImageUploadIdempotency.owner_id == owner_id,
                ImageUploadIdempotency.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def _operation_replay(
        session: Session,
        owner_id: str,
        operation_type: str,
        idempotency_key: str,
    ) -> OperationIdempotency | None:
        return session.scalar(
            select(OperationIdempotency).where(
                OperationIdempotency.owner_id == owner_id,
                OperationIdempotency.operation_type == operation_type,
                OperationIdempotency.idempotency_key == idempotency_key,
            )
        )

    def _replay_image_after_race(
        self, owner_id: str, idempotency_key: str, request_hash: str, now: datetime
    ) -> DraftImage:
        with self.database.session() as session:
            replay = self._image_replay(session, owner_id, idempotency_key)
            if replay is not None and ensure_utc(replay.expires_at) > now:
                if replay.request_hash != request_hash:
                    raise self._idempotency_conflict()
                return DraftImage.model_validate(replay.response_payload)
        raise self._idempotency_conflict()

    def _replay_operation_after_race(
        self,
        owner_id: str,
        operation_type: str,
        idempotency_key: str,
        request_payload: dict[str, object],
        now: datetime,
    ) -> tuple[OperationResponse, bool]:
        with self.database.session() as session:
            replay = self._operation_replay(session, owner_id, operation_type, idempotency_key)
            if replay is not None and ensure_utc(replay.expires_at) > now:
                if replay.request_payload != request_payload:
                    raise self._idempotency_conflict()
                operation = session.get(Operation, replay.operation_id)
                should_schedule = operation is not None and operation.status == "queued"
                return (
                    OperationResponse.model_validate(replay.response_payload),
                    should_schedule,
                )
        raise self._idempotency_conflict()

    def _operation_response(self, operation: Operation) -> OperationResponse:
        return OperationResponse(
            id=operation.id,
            type=operation.type,
            status=operation.status,
            resource_type=operation.resource_type,
            resource_id=operation.resource_id,
            poll_after_seconds=self.settings.ai_operation_poll_after_seconds,
            error=operation.error,
            created_at=ensure_utc(operation.created_at),
            updated_at=ensure_utc(operation.updated_at),
        )

    @staticmethod
    def _idempotency_conflict() -> ApiError:
        return ApiError(
            409,
            "IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used with different data.",
        )

    @staticmethod
    def _version_conflict(current_version: int) -> ApiError:
        return ApiError(
            409,
            "VERSION_CONFLICT",
            "The draft has changed. Refresh it before trying again.",
            {"current_version": current_version},
        )


@lru_cache
def get_media_service() -> MediaService:
    return MediaService(get_settings(), get_database(), get_media_storage())
