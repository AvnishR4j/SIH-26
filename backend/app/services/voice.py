from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

import av
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.db.base import ensure_utc
from app.db.models import (
    CatalogDraft,
    MediaObject,
    Operation,
    OperationIdempotency,
    VoiceMedia,
    VoiceUploadIdempotency,
)
from app.db.session import Database, get_database
from app.schemas.catalog import (
    Draft,
    GenerateListingRequest,
    Listing,
    Transcript,
    VoiceNote,
)
from app.schemas.operations import OperationResponse
from app.services.auth import UserRecord
from app.services.speech import SpeechTranscriber, get_speech_transcriber
from app.storage.local import LocalMediaStorage, get_media_storage

AUDIO_FORMATS = {
    "wav": ("audio/wav", "wav"),
    "mp3": ("audio/mpeg", "mp3"),
    "mov": ("audio/mp4", "m4a"),
    "mp4": ("audio/mp4", "m4a"),
    "m4a": ("audio/mp4", "m4a"),
    "matroska": ("audio/webm", "webm"),
    "webm": ("audio/webm", "webm"),
}


class VoiceService:
    def __init__(
        self,
        settings: Settings,
        database: Database | None = None,
        storage: LocalMediaStorage | None = None,
        transcriber: SpeechTranscriber | None = None,
    ) -> None:
        self.settings = settings
        self.database = database or get_database()
        self.storage = storage or get_media_storage()
        self.transcriber = transcriber or get_speech_transcriber()
        self._lock = self.database.write_lock

    def upload_voice_note(
        self,
        user: UserRecord,
        draft_id: str,
        content: bytes,
        language: str,
        idempotency_key: str,
    ) -> VoiceNote:
        content_type, extension, duration_seconds = self._validate_audio(content)
        if language not in {"hi", "en"}:
            raise ApiError(422, "VALIDATION_ERROR", "Language must be hi or en.")
        request_hash = sha256(content + b"\0language=" + language.encode()).hexdigest()
        now = datetime.now(UTC)
        saved_key: str | None = None

        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = self._voice_replay(session, user.id, idempotency_key)
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        if replay.request_hash != request_hash:
                            raise self._idempotency_conflict()
                        return VoiceNote.model_validate(replay.response_payload)
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    row = self._owned_draft_row(session, user.id, draft_id, lock=True)
                    draft = Draft.model_validate(row.payload)
                    self._ensure_editable(draft)
                    voice_id = f"voice_{uuid4().hex[:12]}"
                    saved_key = f"drafts/{user.id}/{draft.id}/{voice_id}/original.{extension}"
                    self.storage.save(saved_key, content)
                    voice_note = VoiceNote(
                        id=voice_id,
                        language=language,
                        status="uploaded",
                        duration_seconds=duration_seconds,
                        created_at=now,
                    )
                    status = (
                        "media_ready" if draft.status == "draft" and draft.images else draft.status
                    )
                    updated = draft.model_copy(
                        update={
                            "voice_notes": [*draft.voice_notes, voice_note],
                            "status": status,
                            "updated_at": now,
                        }
                    )
                    row.status = updated.status
                    row.payload = updated.model_dump(mode="json")
                    row.updated_at = now
                    session.add(
                        VoiceMedia(
                            id=voice_id,
                            owner_id=user.id,
                            draft_id=draft.id,
                            audio_key=saved_key,
                            content_type=content_type,
                            size_bytes=len(content),
                            sha256=sha256(content).hexdigest(),
                            duration_seconds=duration_seconds,
                            language=language,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    session.flush()
                    session.add(
                        VoiceUploadIdempotency(
                            owner_id=user.id,
                            idempotency_key=idempotency_key,
                            request_hash=request_hash,
                            response_payload=voice_note.model_dump(mode="json"),
                            voice_id=voice_id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    return voice_note
            except IntegrityError:
                if saved_key is not None:
                    self.storage.delete(saved_key)
                return self._replay_voice_after_race(user.id, idempotency_key, request_hash, now)
            except Exception:
                if saved_key is not None:
                    self.storage.delete(saved_key)
                raise

    def start_listing_generation(
        self,
        user: UserRecord,
        draft_id: str,
        request: GenerateListingRequest,
        idempotency_key: str,
    ) -> tuple[OperationResponse, bool]:
        self._require_current_consent(user)
        now = datetime.now(UTC)
        request_payload = {"draft_id": draft_id, **request.model_dump(mode="json")}
        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = self._operation_replay(
                        session, user.id, "generate_listing", idempotency_key
                    )
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        if replay.request_payload != request_payload:
                            raise self._idempotency_conflict()
                        operation = session.get(Operation, replay.operation_id)
                        return (
                            OperationResponse.model_validate(replay.response_payload),
                            operation is not None and operation.status == "queued",
                        )
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    row = self._owned_draft_row(session, user.id, draft_id, lock=True)
                    draft = Draft.model_validate(row.payload)
                    concurrent_replay = self._operation_replay(
                        session, user.id, "generate_listing", idempotency_key
                    )
                    if (
                        concurrent_replay is not None
                        and ensure_utc(concurrent_replay.expires_at) > now
                    ):
                        if concurrent_replay.request_payload != request_payload:
                            raise self._idempotency_conflict()
                        operation = session.get(Operation, concurrent_replay.operation_id)
                        return (
                            OperationResponse.model_validate(concurrent_replay.response_payload),
                            operation is not None and operation.status == "queued",
                        )
                    self._ensure_editable(draft)
                    self._require_voice_note(draft, request.voice_note_id)
                    self._require_image(draft, request.image_id)
                    voice = session.scalar(
                        select(VoiceMedia).where(
                            VoiceMedia.id == request.voice_note_id,
                            VoiceMedia.owner_id == user.id,
                            VoiceMedia.draft_id == draft_id,
                        )
                    )
                    image = session.scalar(
                        select(MediaObject).where(
                            MediaObject.id == request.image_id,
                            MediaObject.owner_id == user.id,
                            MediaObject.draft_id == draft_id,
                        )
                    )
                    if voice is None or image is None:
                        raise ApiError(404, "NOT_FOUND", "The requested draft media was not found.")
                    active = session.scalar(
                        select(Operation.id).where(
                            Operation.owner_id == user.id,
                            Operation.resource_id == draft_id,
                            Operation.type == "generate_listing",
                            Operation.status.in_(("queued", "running")),
                        )
                    )
                    if active is not None:
                        raise ApiError(
                            409,
                            "INVALID_STATE",
                            "Listing generation is already in progress for this draft.",
                        )

                    operation_id = f"op_{uuid4().hex[:12]}"
                    response = OperationResponse(
                        id=operation_id,
                        type="generate_listing",
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
                            type="generate_listing",
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
                            operation_type="generate_listing",
                            idempotency_key=idempotency_key,
                            request_payload=request_payload,
                            response_payload=response.model_dump(mode="json"),
                            operation_id=operation_id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    updated = draft.model_copy(
                        update={
                            "status": "processing",
                            "last_processing_error": None,
                            "updated_at": now,
                        }
                    )
                    row.status = updated.status
                    row.payload = updated.model_dump(mode="json")
                    row.updated_at = now
                    return response, True
            except IntegrityError:
                return self._replay_operation_after_race(
                    user.id,
                    idempotency_key,
                    request_payload,
                    now,
                )

    def complete_listing_generation(self, owner_id: str, operation_id: str) -> None:
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
                voice = session.scalar(
                    select(VoiceMedia).where(
                        VoiceMedia.id == payload["voice_note_id"],
                        VoiceMedia.owner_id == owner_id,
                    )
                )
                if voice is None:
                    raise ApiError(404, "NOT_FOUND", "The voice note was not found.")
                audio_key = voice.audio_key
                language = voice.language

            result = self.transcriber.transcribe(self.storage.read(audio_key), language)
            now = datetime.now(UTC)
            with self._lock, self.database.session() as session, session.begin():
                operation = session.get(Operation, operation_id)
                row = self._owned_draft_row(session, owner_id, str(payload["draft_id"]), lock=True)
                if operation is None or operation.status != "running":
                    return
                draft = Draft.model_validate(row.payload)
                listing = self._grounded_listing(
                    draft,
                    result.text,
                    result.language,
                    list(payload["target_languages"]),
                )
                missing_fields = [
                    name for name, value in draft.fields.model_dump().items() if value is None
                ]
                updated = draft.model_copy(
                    update={
                        "version": draft.version + 1,
                        "status": "needs_confirmation",
                        "listing": listing,
                        "transcript": Transcript(
                            voice_note_id=str(payload["voice_note_id"]),
                            language=result.language,
                            text=result.text,
                        ),
                        "missing_fields": missing_fields,
                        "last_processing_error": None,
                        "updated_at": now,
                    }
                )
                row.version = updated.version
                row.status = updated.status
                row.payload = updated.model_dump(mode="json")
                row.updated_at = now
                operation.status = "succeeded"
                operation.error = None
                operation.updated_at = now
        # Background work must always leave a terminal operation that the client can poll.
        except Exception as error:  # noqa: BLE001
            self._record_generation_failure(owner_id, operation_id, error)

    def _record_generation_failure(
        self, owner_id: str, operation_id: str, error: Exception
    ) -> None:
        if isinstance(error, ApiError):
            failure = {
                "code": error.code,
                "message": error.message,
                "details": error.details,
            }
        else:
            failure = {
                "code": "INTERNAL_ERROR",
                "message": "Listing generation failed.",
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
            updated = draft.model_copy(
                update={
                    "status": "failed",
                    "last_processing_error": failure,
                    "updated_at": now,
                }
            )
            row.status = updated.status
            row.payload = updated.model_dump(mode="json")
            row.updated_at = now

    def _validate_audio(self, content: bytes) -> tuple[str, str, int]:
        if not content:
            raise ApiError(422, "VALIDATION_ERROR", "The audio file is empty.")
        if len(content) > self.settings.max_audio_bytes:
            raise ApiError(
                413,
                "UPLOAD_TOO_LARGE",
                "The audio exceeds the configured upload limit.",
                {"max_bytes": self.settings.max_audio_bytes},
            )
        try:
            with av.open(BytesIO(content), mode="r") as container:
                format_names = set(container.format.name.split(","))
                audio_format = next(
                    (AUDIO_FORMATS[name] for name in format_names if name in AUDIO_FORMATS),
                    None,
                )
                if audio_format is None or not container.streams.audio:
                    raise ApiError(
                        415,
                        "UNSUPPORTED_MEDIA_TYPE",
                        "Upload a valid M4A, MP3, WAV, or WebM audio file.",
                    )
                duration = 0.0
                for frame in container.decode(audio=0):
                    if frame.sample_rate and frame.samples:
                        duration += frame.samples / frame.sample_rate
                    if duration > self.settings.max_audio_duration_seconds:
                        raise ApiError(
                            413,
                            "UPLOAD_TOO_LARGE",
                            "The audio exceeds the configured duration limit.",
                            {"max_duration_seconds": self.settings.max_audio_duration_seconds},
                        )
        except ApiError:
            raise
        except Exception as error:
            raise ApiError(
                415,
                "UNSUPPORTED_MEDIA_TYPE",
                "Upload a valid M4A, MP3, WAV, or WebM audio file.",
            ) from error
        if duration <= 0:
            raise ApiError(422, "VALIDATION_ERROR", "The audio file contains no samples.")
        return (*audio_format, max(1, math.ceil(duration)))

    @staticmethod
    def _grounded_listing(
        draft: Draft,
        text: str,
        language: str,
        target_languages: list[str],
    ) -> Listing:
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
            if language == "hi":
                description_hi = description_hi or text
        if "en" in target_languages:
            title_en = title_en or draft.craft_category
            if language == "en":
                description_en = description_en or text
        tags = existing.tags or [draft.craft_category]
        return Listing(
            title_hi=title_hi,
            title_en=title_en,
            description_hi=description_hi,
            description_en=description_en,
            tags=tags,
        )

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
    def _require_voice_note(draft: Draft, voice_id: str) -> None:
        if not any(note.id == voice_id for note in draft.voice_notes):
            raise ApiError(404, "NOT_FOUND", "The voice note was not found.")

    @staticmethod
    def _require_image(draft: Draft, image_id: str) -> None:
        if not any(image.id == image_id for image in draft.images):
            raise ApiError(404, "NOT_FOUND", "The image was not found.")

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
    def _voice_replay(
        session: Session, owner_id: str, idempotency_key: str
    ) -> VoiceUploadIdempotency | None:
        return session.scalar(
            select(VoiceUploadIdempotency).where(
                VoiceUploadIdempotency.owner_id == owner_id,
                VoiceUploadIdempotency.idempotency_key == idempotency_key,
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

    def _replay_voice_after_race(
        self, owner_id: str, idempotency_key: str, request_hash: str, now: datetime
    ) -> VoiceNote:
        with self.database.session() as session:
            replay = self._voice_replay(session, owner_id, idempotency_key)
            if replay is not None and ensure_utc(replay.expires_at) > now:
                if replay.request_hash != request_hash:
                    raise self._idempotency_conflict()
                return VoiceNote.model_validate(replay.response_payload)
        raise self._idempotency_conflict()

    def _replay_operation_after_race(
        self,
        owner_id: str,
        idempotency_key: str,
        request_payload: dict[str, object],
        now: datetime,
    ) -> tuple[OperationResponse, bool]:
        with self.database.session() as session:
            replay = self._operation_replay(session, owner_id, "generate_listing", idempotency_key)
            if replay is not None and ensure_utc(replay.expires_at) > now:
                if replay.request_payload != request_payload:
                    raise self._idempotency_conflict()
                operation = session.get(Operation, replay.operation_id)
                return (
                    OperationResponse.model_validate(replay.response_payload),
                    operation is not None and operation.status == "queued",
                )
        raise self._idempotency_conflict()

    @staticmethod
    def _idempotency_conflict() -> ApiError:
        return ApiError(
            409,
            "IDEMPOTENCY_CONFLICT",
            "This idempotency key was already used with different data.",
        )


@lru_cache
def get_voice_service() -> VoiceService:
    return VoiceService(
        get_settings(),
        get_database(),
        get_media_storage(),
        get_speech_transcriber(),
    )
