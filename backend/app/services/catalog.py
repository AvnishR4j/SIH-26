from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from time import monotonic
from uuid import uuid4

from pydantic import ValidationError

from app.core.errors import ApiError
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

IDEMPOTENCY_TTL_SECONDS = 24 * 60 * 60


@dataclass
class StoredDraft:
    owner_id: str
    draft: Draft


@dataclass
class CreateReplay:
    request: DraftCreate
    draft_id: str
    expires_at: float


class CatalogService:
    def __init__(self) -> None:
        self.drafts: dict[str, StoredDraft] = {}
        self.create_replays: dict[tuple[str, str], CreateReplay] = {}

    def reset(self) -> None:
        self.drafts.clear()
        self.create_replays.clear()

    def create_draft(self, user: UserRecord, request: DraftCreate, idempotency_key: str) -> Draft:
        scope = (user.id, idempotency_key)
        replay = self.create_replays.get(scope)
        if replay and replay.expires_at > monotonic():
            if replay.request != request:
                raise ApiError(
                    409,
                    "IDEMPOTENCY_CONFLICT",
                    "This idempotency key was already used with different data.",
                )
            return self.drafts[replay.draft_id].draft

        now = datetime.now(UTC)
        draft = Draft(
            id=f"draft_{uuid4().hex[:12]}",
            version=1,
            status="draft",
            craft_category=request.craft_category,
            source_language=request.source_language,
            initial_notes=request.initial_notes,
            fields=ProductFields(),
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
        self.drafts[draft.id] = StoredDraft(owner_id=user.id, draft=draft)
        self.create_replays[scope] = CreateReplay(
            request=request.model_copy(deep=True),
            draft_id=draft.id,
            expires_at=monotonic() + IDEMPOTENCY_TTL_SECONDS,
        )
        return draft

    def list_drafts(
        self,
        user: UserRecord,
        limit: int,
        cursor: str | None,
        status: DraftStatus | None,
    ) -> DraftList:
        drafts = [
            item.draft
            for item in self.drafts.values()
            if item.owner_id == user.id and (status is None or item.draft.status == status)
        ]
        drafts.sort(key=lambda draft: (draft.updated_at, draft.id), reverse=True)

        if cursor is not None:
            cursor_time, cursor_id = self._decode_cursor(cursor)
            drafts = [
                draft for draft in drafts if (draft.updated_at, draft.id) < (cursor_time, cursor_id)
            ]

        page = drafts[:limit]
        next_cursor = None
        if len(drafts) > limit:
            last = page[-1]
            next_cursor = self._encode_cursor(last.updated_at, last.id)
        return DraftList(items=[self._summary(draft) for draft in page], next_cursor=next_cursor)

    def get_draft(self, user: UserRecord, draft_id: str) -> Draft:
        return self._owned_draft(user, draft_id)

    def update_draft(self, user: UserRecord, draft_id: str, request: DraftPatch) -> Draft:
        draft = self._owned_draft(user, draft_id)
        if draft.status == "approved":
            raise ApiError(400, "INVALID_STATE", "An approved draft cannot be changed.")
        if request.version != draft.version:
            raise ApiError(
                409,
                "VERSION_CONFLICT",
                "The draft has changed. Refresh it before trying again.",
                {"current_version": draft.version},
            )

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
                key: value for key, value in draft.field_confidence.items() if key not in confirmed
            }
            updates["missing_fields"] = [
                field for field in draft.missing_fields if field not in confirmed
            ]
        if request.listing is not None:
            supplied_listing = request.listing.model_dump(exclude_unset=True)
            current_listing = draft.listing or Listing()
            updates["listing"] = current_listing.model_copy(update=supplied_listing)

        updated = draft.model_copy(update=updates)
        self.drafts[draft_id].draft = updated
        return updated

    def _owned_draft(self, user: UserRecord, draft_id: str) -> Draft:
        stored = self.drafts.get(draft_id)
        if stored is None or stored.owner_id != user.id:
            raise ApiError(404, "NOT_FOUND", "The draft was not found.")
        return stored.draft

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
    return CatalogService()
