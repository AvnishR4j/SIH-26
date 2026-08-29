from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import and_, delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.db.base import ensure_utc
from app.db.models import CatalogDraft, DraftCreateIdempotency
from app.db.session import Database, get_database
from app.schemas.catalog import (
    Draft,
    DraftCreate,
    DraftList,
    DraftPatch,
    DraftStatus,
    DraftSummary,
    Listing,
    ProductFields,
)
from app.services.auth import UserRecord


class CatalogService:
    def __init__(self, settings: Settings, database: Database | None = None) -> None:
        self.settings = settings
        self.database = database or get_database()
        self._lock = self.database.write_lock

    def reset(self) -> None:
        with self._lock, self.database.session() as session, session.begin():
            session.execute(delete(DraftCreateIdempotency))
            session.execute(delete(CatalogDraft))

    def create_draft(self, user: UserRecord, request: DraftCreate, idempotency_key: str) -> Draft:
        now = datetime.now(UTC)
        request_payload = request.model_dump(mode="json")
        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = session.scalar(
                        select(DraftCreateIdempotency).where(
                            DraftCreateIdempotency.owner_id == user.id,
                            DraftCreateIdempotency.idempotency_key == idempotency_key,
                        )
                    )
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        if replay.request_payload != request_payload:
                            raise self._idempotency_conflict()
                        row = session.get(CatalogDraft, replay.draft_id)
                        if row is None:
                            raise ApiError(
                                500, "INTERNAL_ERROR", "The draft replay is unavailable."
                            )
                        return self._draft(row)
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    draft = self._new_draft(request, now)
                    session.add(
                        CatalogDraft(
                            id=draft.id,
                            owner_id=user.id,
                            version=draft.version,
                            status=draft.status,
                            payload=draft.model_dump(mode="json"),
                            created_at=draft.created_at,
                            updated_at=draft.updated_at,
                        )
                    )
                    session.add(
                        DraftCreateIdempotency(
                            owner_id=user.id,
                            idempotency_key=idempotency_key,
                            request_payload=request_payload,
                            draft_id=draft.id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    return draft
            except IntegrityError:
                return self._replay_after_concurrent_create(
                    user.id, idempotency_key, request_payload, now
                )

    def list_drafts(
        self,
        user: UserRecord,
        limit: int,
        cursor: str | None,
        status: DraftStatus | None,
    ) -> DraftList:
        statement = select(CatalogDraft).where(CatalogDraft.owner_id == user.id)
        if status is not None:
            statement = statement.where(CatalogDraft.status == status)
        if cursor is not None:
            cursor_time, cursor_id = self._decode_cursor(cursor)
            statement = statement.where(
                or_(
                    CatalogDraft.updated_at < cursor_time,
                    and_(
                        CatalogDraft.updated_at == cursor_time,
                        CatalogDraft.id < cursor_id,
                    ),
                )
            )
        statement = statement.order_by(
            CatalogDraft.updated_at.desc(), CatalogDraft.id.desc()
        ).limit(limit + 1)

        with self.database.session() as session:
            rows = list(session.scalars(statement))
        has_next = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if has_next:
            last = page[-1]
            next_cursor = self._encode_cursor(ensure_utc(last.updated_at), last.id)
        return DraftList(
            items=[self._summary(self._draft(row)) for row in page],
            next_cursor=next_cursor,
        )

    def get_draft(self, user: UserRecord, draft_id: str) -> Draft:
        with self.database.session() as session:
            return self._owned_draft(session, user.id, draft_id)

    def update_draft(self, user: UserRecord, draft_id: str, request: DraftPatch) -> Draft:
        with self._lock, self.database.session() as session, session.begin():
            draft = self._owned_draft(session, user.id, draft_id)
            if draft.status == "approved":
                raise ApiError(400, "INVALID_STATE", "An approved draft cannot be changed.")
            if request.version != draft.version:
                raise self._version_conflict(draft.version)

            updates: dict[str, object] = {
                "version": draft.version + 1,
                "updated_at": datetime.now(UTC),
            }
            if request.fields is not None:
                supplied = request.fields.model_dump(exclude_unset=True)
                updates["fields"] = draft.fields.model_copy(update=supplied)
                confirmed = {
                    key for key, value in supplied.items() if value is not None and value != ""
                }
                updates["field_confidence"] = {
                    key: value
                    for key, value in draft.field_confidence.items()
                    if key not in confirmed
                }
                updates["missing_fields"] = [
                    field for field in draft.missing_fields if field not in confirmed
                ]
            if request.listing is not None:
                supplied_listing = request.listing.model_dump(exclude_unset=True)
                current_listing = draft.listing or Listing(
                    title_hi=None,
                    title_en=None,
                    description_hi=None,
                    description_en=None,
                    tags=[],
                )
                updates["listing"] = current_listing.model_copy(update=supplied_listing)

            updated = draft.model_copy(update=updates)
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
                    updated_at=updated.updated_at,
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
            return updated

    def _owned_draft(self, session: Session, owner_id: str, draft_id: str) -> Draft:
        row = session.scalar(
            select(CatalogDraft).where(
                CatalogDraft.id == draft_id,
                CatalogDraft.owner_id == owner_id,
            )
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "The draft was not found.")
        return self._draft(row)

    def _replay_after_concurrent_create(
        self,
        owner_id: str,
        idempotency_key: str,
        request_payload: dict[str, object],
        now: datetime,
    ) -> Draft:
        with self.database.session() as session:
            replay = session.scalar(
                select(DraftCreateIdempotency).where(
                    DraftCreateIdempotency.owner_id == owner_id,
                    DraftCreateIdempotency.idempotency_key == idempotency_key,
                )
            )
            if replay is not None and ensure_utc(replay.expires_at) > now:
                if replay.request_payload != request_payload:
                    raise self._idempotency_conflict()
                row = session.get(CatalogDraft, replay.draft_id)
                if row is not None:
                    return self._draft(row)
        raise self._idempotency_conflict()

    @staticmethod
    def _new_draft(request: DraftCreate, now: datetime) -> Draft:
        return Draft(
            id=f"draft_{uuid4().hex[:12]}",
            version=1,
            status="draft",
            craft_category=request.craft_category,
            source_language=request.source_language,
            initial_notes=request.initial_notes,
            fields=ProductFields(
                product_type=None,
                material=None,
                technique=None,
                color=None,
                dimensions=None,
                quantity_available=None,
                production_time_days=None,
                care=None,
                origin=None,
            ),
            listing=None,
            images=[],
            voice_notes=[],
            transcript=None,
            field_confidence={},
            missing_fields=[],
            pricing=None,
            last_processing_error=None,
            created_at=now,
            updated_at=now,
        )

    @staticmethod
    def _draft(row: CatalogDraft) -> Draft:
        return Draft.model_validate(row.payload)

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

    @staticmethod
    def _summary(draft: Draft) -> DraftSummary:
        primary = next((image for image in draft.images if image.is_primary), None)
        thumbnail_url = None
        if primary is not None:
            thumbnail_url = (
                primary.enhanced_url
                if primary.selected_variant == "enhanced"
                else primary.original_url
            )
        return DraftSummary(
            id=draft.id,
            version=draft.version,
            status=draft.status,
            title_hi=draft.listing.title_hi if draft.listing else None,
            title_en=draft.listing.title_en if draft.listing else None,
            thumbnail_url=thumbnail_url,
            recommended_price_paise=(draft.pricing.recommended_paise if draft.pricing else None),
            updated_at=draft.updated_at,
        )

    @staticmethod
    def _encode_cursor(updated_at: datetime, draft_id: str) -> str:
        value = f"{updated_at.isoformat()}|{draft_id}".encode()
        return urlsafe_b64encode(value).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> tuple[datetime, str]:
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = urlsafe_b64decode(cursor + padding).decode()
            timestamp, draft_id = decoded.rsplit("|", 1)
            updated_at = datetime.fromisoformat(timestamp)
            if updated_at.tzinfo is None or not draft_id.startswith("draft_"):
                raise ValueError
            return updated_at, draft_id
        except (Base64Error, UnicodeDecodeError, ValueError, ValidationError) as error:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "The pagination cursor is invalid.",
                {"fields": {"cursor": "Use the cursor returned by the previous response."}},
            ) from error


@lru_cache
def get_catalog_service() -> CatalogService:
    return CatalogService(get_settings(), get_database())
