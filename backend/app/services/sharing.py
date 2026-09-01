from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from binascii import Error as Base64Error
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import uuid4

from sqlalchemy import and_, func, or_, select, update
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
    EnquiryIdempotency,
    MediaObject,
    Operation,
)
from app.db.session import Database, get_database
from app.schemas.catalog import Draft
from app.schemas.sharing import (
    ApprovalRequest,
    ApprovedCatalog,
    EnquiryRequest,
    EnquiryResponse,
    MarketplaceCatalogue,
    MarketplaceCataloguePage,
    PublicArtisan,
    PublicShareCard,
    ShopifyProductSync,
)
from app.services.auth import UserRecord
from app.services.shopify import ShopifyDraftProduct, ShopifyService, get_shopify_service
from app.storage.base import MediaStorage
from app.storage.factory import create_media_storage, get_media_storage


class SharingService:
    def __init__(
        self,
        settings: Settings,
        database: Database | None = None,
        storage: MediaStorage | None = None,
        shopify: ShopifyService | None = None,
    ) -> None:
        self.settings = settings
        self.database = database or get_database()
        self.storage = storage or create_media_storage(settings)
        self.shopify = shopify or get_shopify_service()
        self._lock = self.database.write_lock

    def approve_draft(
        self,
        user: UserRecord,
        draft_id: str,
        request: ApprovalRequest,
        idempotency_key: str,
    ) -> ApprovedCatalog:
        now = datetime.now(UTC)
        request_payload = {"draft_id": draft_id, **request.model_dump(mode="json")}
        published_key: str | None = None
        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = self._approval_replay(session, user.id, idempotency_key)
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        self._assert_same_request(replay.request_payload, request_payload)
                        return ApprovedCatalog.model_validate(replay.response_payload)
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    row = self._owned_draft_row(session, user.id, draft_id)
                    draft = Draft.model_validate(row.payload)
                    if draft.status == "approved":
                        concurrent_replay = self._approval_replay(session, user.id, idempotency_key)
                        if (
                            concurrent_replay is not None
                            and ensure_utc(concurrent_replay.expires_at) > now
                        ):
                            self._assert_same_request(
                                concurrent_replay.request_payload, request_payload
                            )
                            return ApprovedCatalog.model_validate(
                                concurrent_replay.response_payload
                            )
                        raise ApiError(
                            400,
                            "INVALID_STATE",
                            "An approved draft cannot be approved again.",
                        )
                    if draft.version != request.version:
                        raise self._version_conflict(draft.version)

                    missing = self._missing_readiness(session, user.id, draft)
                    if missing:
                        raise ApiError(
                            400,
                            "INVALID_STATE",
                            "The draft is not ready for approval.",
                            {"fields": missing},
                        )
                    assert draft.pricing is not None
                    outside_range = not (
                        draft.pricing.suggested_min_paise
                        <= request.approved_price_paise
                        <= draft.pricing.suggested_max_paise
                    )
                    if outside_range and request.price_override_reason is None:
                        raise ApiError(
                            422,
                            "VALIDATION_ERROR",
                            "A reason is required when overriding the suggested range.",
                            {
                                "fields": {
                                    "price_override_reason": (
                                        "Required when the approved price is outside the "
                                        "suggested range."
                                    )
                                }
                            },
                        )

                    snapshot, response, published_key = self._build_snapshot(
                        session,
                        user,
                        draft,
                        request,
                        now,
                    )
                    session.add(snapshot)
                    approved_draft = draft.model_copy(
                        update={
                            "version": draft.version + 1,
                            "status": "approved",
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
                            version=approved_draft.version,
                            status="approved",
                            payload=approved_draft.model_dump(mode="json"),
                            updated_at=now,
                        )
                    )
                    if result.rowcount != 1:
                        current = session.scalar(
                            select(CatalogDraft.version).where(CatalogDraft.id == draft_id)
                        )
                        raise self._version_conflict(current or draft.version)
                    session.add(
                        ApprovalIdempotency(
                            owner_id=user.id,
                            idempotency_key=idempotency_key,
                            request_payload=request_payload,
                            response_payload=response.model_dump(mode="json"),
                            catalog_id=snapshot.id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
            except IntegrityError:
                if published_key is not None:
                    self.storage.delete(published_key)
                return self._approval_replay_after_race(
                    user.id,
                    idempotency_key,
                    request_payload,
                    now,
                )
            except Exception:
                if published_key is not None:
                    self.storage.delete(published_key)
                raise
        return response

    def delete_marketplace_catalogue(self, user: UserRecord, public_share_id: str) -> None:
        if user.role != "admin":
            raise ApiError(403, "FORBIDDEN", "Only an admin can delete marketplace catalogues.")
        with self._lock, self.database.session() as session, session.begin():
            snapshot = session.scalar(
                select(CatalogSnapshot).where(
                    CatalogSnapshot.public_share_id == public_share_id,
                    CatalogSnapshot.is_deleted.is_(False),
                )
            )
            if snapshot is None:
                raise ApiError(404, "NOT_FOUND", "The catalogue was not found.")
            now = datetime.now(UTC)
            snapshot.is_deleted = True
            session.execute(
                update(CatalogDraft)
                .where(
                    CatalogDraft.id == snapshot.draft_id,
                    CatalogDraft.is_deleted.is_(False),
                )
                .values(is_deleted=True, updated_at=now)
            )

    def get_approved_catalog(self, user: UserRecord, draft_id: str) -> ApprovedCatalog:
        with self.database.session() as session:
            snapshot = session.scalar(
                select(CatalogSnapshot).where(
                    CatalogSnapshot.draft_id == draft_id,
                    CatalogSnapshot.owner_id == user.id,
                    CatalogSnapshot.is_deleted.is_(False),
                )
            )
            if snapshot is None:
                raise ApiError(404, "NOT_FOUND", "Published catalogue not found.")
            return ApprovedCatalog(
                id=snapshot.id,
                draft_id=snapshot.draft_id,
                status="approved",
                approved_price_paise=snapshot.approved_price_paise,
                currency="INR",
                public_share_id=snapshot.public_share_id,
                public_share_url=(
                    f"{self.settings.public_share_web_base_url}/share/{snapshot.public_share_id}"
                ),
                created_at=ensure_utc(snapshot.created_at),
            )

    def sync_draft_to_shopify(self, user: UserRecord, draft_id: str) -> ShopifyProductSync:
        """Create one Shopify Draft product from an already approved catalogue."""
        with self._lock, self.database.session() as session:
            snapshot = session.scalar(
                select(CatalogSnapshot).where(
                    CatalogSnapshot.draft_id == draft_id,
                    CatalogSnapshot.owner_id == user.id,
                    CatalogSnapshot.is_deleted.is_(False),
                )
            )
            if snapshot is None:
                raise ApiError(404, "NOT_FOUND", "Published catalogue not found.")
            if snapshot.shopify_product_id is not None:
                return self._shopify_sync_response(snapshot)
            row = self._owned_draft_row(session, user.id, draft_id)
            draft = Draft.model_validate(row.payload)
            if draft.listing is None:
                raise ApiError(400, "INVALID_STATE", "The catalogue has no listing details.")
            image_content = self.storage.read(snapshot.public_image_key)
            product = ShopifyDraftProduct(
                title=draft.listing.title_en or draft.listing.title_hi or "KalaSetu product",
                description_html=self._shopify_description(draft),
                vendor=user.name,
                product_type=draft.fields.product_type or draft.craft_category,
                tags=self._shopify_tags(draft),
                price_paise=snapshot.approved_price_paise,
                image_filename=snapshot.public_image_key.rsplit("/", 1)[-1],
                image_content=image_content,
            )

            created = self.shopify.create_draft_product(product)
            synced_at = datetime.now(UTC)
            snapshot.shopify_product_id = created.product_id
            snapshot.shopify_product_handle = created.handle
            snapshot.shopify_synced_at = synced_at
            session.commit()
            return self._shopify_sync_response(snapshot)

    def get_share_card(self, public_share_id: str) -> PublicShareCard:
        with self.database.session() as session:
            snapshot = session.scalar(
                select(CatalogSnapshot).where(
                    CatalogSnapshot.public_share_id == public_share_id,
                    CatalogSnapshot.is_deleted.is_(False),
                )
            )
            if snapshot is None:
                raise ApiError(404, "NOT_FOUND", "The shared catalogue was not found.")
            return PublicShareCard.model_validate(snapshot.payload)

    def list_marketplace_catalogues(
        self, limit: int, cursor: str | None
    ) -> MarketplaceCataloguePage:
        statement = select(CatalogSnapshot).where(CatalogSnapshot.is_deleted.is_(False))
        if cursor is not None:
            cursor_time, cursor_id = self._decode_marketplace_cursor(cursor)
            statement = statement.where(
                or_(
                    CatalogSnapshot.created_at < cursor_time,
                    and_(
                        CatalogSnapshot.created_at == cursor_time,
                        CatalogSnapshot.id < cursor_id,
                    ),
                )
            )
        statement = statement.order_by(
            CatalogSnapshot.created_at.desc(), CatalogSnapshot.id.desc()
        ).limit(limit + 1)
        with self.database.session() as session:
            rows = list(session.scalars(statement))
            page = rows[:limit]
            next_cursor = None
            if len(rows) > limit:
                last = page[-1]
                next_cursor = self._encode_marketplace_cursor(ensure_utc(last.created_at), last.id)
            return MarketplaceCataloguePage(
                items=[self._marketplace_catalogue(row) for row in page],
                next_cursor=next_cursor,
            )

    def submit_enquiry(
        self,
        public_share_id: str,
        request: EnquiryRequest,
        idempotency_key: str,
    ) -> EnquiryResponse:
        now = datetime.now(UTC)
        request_payload = request.model_dump(mode="json")
        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = self._enquiry_replay(session, public_share_id, idempotency_key)
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        self._assert_same_request(replay.request_payload, request_payload)
                        return EnquiryResponse.model_validate(replay.response_payload)
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    snapshot = session.scalar(
                        select(CatalogSnapshot)
                        .where(
                            CatalogSnapshot.public_share_id == public_share_id,
                            CatalogSnapshot.is_deleted.is_(False),
                        )
                        .with_for_update()
                    )
                    if snapshot is None:
                        raise ApiError(404, "NOT_FOUND", "The shared catalogue was not found.")
                    concurrent_replay = self._enquiry_replay(
                        session, public_share_id, idempotency_key
                    )
                    if (
                        concurrent_replay is not None
                        and ensure_utc(concurrent_replay.expires_at) > now
                    ):
                        self._assert_same_request(
                            concurrent_replay.request_payload, request_payload
                        )
                        return EnquiryResponse.model_validate(concurrent_replay.response_payload)
                    window_start = now - timedelta(hours=1)
                    recent_count = session.scalar(
                        select(func.count(BuyerEnquiry.id)).where(
                            BuyerEnquiry.catalog_id == snapshot.id,
                            BuyerEnquiry.buyer_phone == request.buyer_phone,
                            BuyerEnquiry.created_at >= window_start,
                        )
                    )
                    if (recent_count or 0) >= self.settings.enquiry_max_per_hour_per_buyer:
                        raise ApiError(
                            429,
                            "RATE_LIMITED",
                            "Too many enquiries. Please try again later.",
                            {"retry_after_seconds": 3600},
                            {"Retry-After": "3600"},
                        )

                    enquiry_id = f"enq_{uuid4().hex[:16]}"
                    response = EnquiryResponse(
                        enquiry_id=enquiry_id,
                        status="received",
                        received_at=now,
                    )
                    session.add(
                        BuyerEnquiry(
                            id=enquiry_id,
                            catalog_id=snapshot.id,
                            buyer_name=request.buyer_name,
                            buyer_phone=request.buyer_phone,
                            message=request.message,
                            quantity_requested=request.quantity_requested,
                            consent_to_contact=True,
                            created_at=now,
                        )
                    )
                    session.add(
                        EnquiryIdempotency(
                            public_share_id=public_share_id,
                            idempotency_key=idempotency_key,
                            request_payload=request_payload,
                            response_payload=response.model_dump(mode="json"),
                            enquiry_id=enquiry_id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    return response
            except IntegrityError:
                return self._enquiry_replay_after_race(
                    public_share_id,
                    idempotency_key,
                    request_payload,
                    now,
                )

    def _build_snapshot(
        self,
        session: Session,
        user: UserRecord,
        draft: Draft,
        request: ApprovalRequest,
        now: datetime,
    ) -> tuple[CatalogSnapshot, ApprovedCatalog, str]:
        assert draft.listing is not None
        assert draft.fields.quantity_available is not None
        primary = next(image for image in draft.images if image.is_primary)
        catalog_id = f"cat_{uuid4().hex[:16]}"
        public_share_id = f"share_{uuid4().hex}"
        media = session.scalar(
            select(MediaObject).where(
                MediaObject.id == primary.id,
                MediaObject.draft_id == draft.id,
                MediaObject.owner_id == user.id,
            )
        )
        if media is None:
            raise ApiError(500, "INTERNAL_ERROR", "The selected image is unavailable.")
        source_key = (
            media.enhanced_key if primary.selected_variant == "enhanced" else media.original_key
        )
        if source_key is None:
            raise ApiError(500, "INTERNAL_ERROR", "The selected image is unavailable.")
        suffix = source_key.rsplit(".", 1)[-1]
        public_image_key = f"public/{public_share_id}/product.{suffix}"
        self.storage.save(public_image_key, self.storage.read(source_key))
        try:
            image_url = self.storage.url(public_image_key)
            card = PublicShareCard(
                catalog_id=catalog_id,
                title=draft.listing.title_en or draft.listing.title_hi or "",
                description=(draft.listing.description_en or draft.listing.description_hi or ""),
                image_url=image_url,
                price_paise=request.approved_price_paise,
                currency="INR",
                quantity_available=draft.fields.quantity_available,
                artisan=PublicArtisan(display_name=user.name, cluster=user.cluster),
                enquiry_enabled=True,
                published_at=now,
            )
            snapshot = CatalogSnapshot(
                id=catalog_id,
                draft_id=draft.id,
                owner_id=user.id,
                public_share_id=public_share_id,
                public_image_key=public_image_key,
                source_draft_version=draft.version,
                approved_price_paise=request.approved_price_paise,
                price_override_reason=request.price_override_reason,
                approval_note=request.approval_note,
                payload=card.model_dump(mode="json"),
                created_at=now,
            )
            response = ApprovedCatalog(
                id=catalog_id,
                draft_id=draft.id,
                status="approved",
                approved_price_paise=request.approved_price_paise,
                currency="INR",
                public_share_id=public_share_id,
                public_share_url=(
                    f"{self.settings.public_share_web_base_url}/share/{public_share_id}"
                ),
                created_at=now,
            )
            return snapshot, response, public_image_key
        except Exception:
            self.storage.delete(public_image_key)
            raise

    @staticmethod
    def _marketplace_catalogue(snapshot: CatalogSnapshot) -> MarketplaceCatalogue:
        card = PublicShareCard.model_validate(snapshot.payload)
        return MarketplaceCatalogue(
            public_share_id=snapshot.public_share_id,
            title=card.title,
            description=card.description,
            image_url=card.image_url,
            price_paise=card.price_paise,
            currency=card.currency,
            quantity_available=card.quantity_available,
            artisan=card.artisan,
            published_at=card.published_at,
        )

    def _shopify_sync_response(self, snapshot: CatalogSnapshot) -> ShopifyProductSync:
        assert snapshot.shopify_product_id is not None
        numeric_id = snapshot.shopify_product_id.rsplit("/", 1)[-1]
        return ShopifyProductSync(
            catalog_id=snapshot.id,
            shopify_product_id=snapshot.shopify_product_id,
            shopify_product_handle=snapshot.shopify_product_handle,
            admin_url=f"https://{self.settings.shopify_store_domain}/admin/products/{numeric_id}",
            status="draft",
            synced_at=ensure_utc(snapshot.shopify_synced_at),
        )

    @staticmethod
    def _shopify_tags(draft: Draft) -> list[str]:
        candidates = [
            *(draft.listing.tags if draft.listing is not None else []),
            draft.craft_category,
            draft.fields.material or "",
            draft.fields.technique or "",
            "KalaSetu",
        ]
        return list(dict.fromkeys(value.strip() for value in candidates if value.strip()))[:20]

    @staticmethod
    def _shopify_description(draft: Draft) -> str:
        assert draft.listing is not None
        description = draft.listing.description_en or draft.listing.description_hi or ""
        details = [
            ("Material", draft.fields.material),
            ("Technique", draft.fields.technique),
            ("Dimensions", draft.fields.dimensions),
            ("Production time", f"{draft.fields.production_time_days} days"
             if draft.fields.production_time_days is not None else None),
        ]
        detail_html = "".join(
            f"<li><strong>{label}:</strong> {value}</li>" for label, value in details if value
        )
        return f"<p>{description}</p><ul>{detail_html}</ul>"

    @staticmethod
    def _encode_marketplace_cursor(created_at: datetime, catalog_id: str) -> str:
        value = f"{created_at.isoformat()}|{catalog_id}".encode()
        return urlsafe_b64encode(value).decode().rstrip("=")

    @staticmethod
    def _decode_marketplace_cursor(cursor: str) -> tuple[datetime, str]:
        try:
            padding = "=" * (-len(cursor) % 4)
            decoded = urlsafe_b64decode(cursor + padding).decode()
            timestamp, catalog_id = decoded.rsplit("|", 1)
            created_at = datetime.fromisoformat(timestamp)
            if created_at.tzinfo is None or not catalog_id.startswith("cat_"):
                raise ValueError
            return created_at, catalog_id
        except (Base64Error, UnicodeDecodeError, ValueError) as error:
            raise ApiError(
                422,
                "VALIDATION_ERROR",
                "The pagination cursor is invalid.",
                {"fields": {"cursor": "Use the cursor returned by the previous response."}},
            ) from error

    @staticmethod
    def _missing_readiness(session: Session, owner_id: str, draft: Draft) -> list[str]:
        fields: list[str] = []
        required = {
            "craft_category": draft.craft_category,
            "product_type": draft.fields.product_type,
            "material": draft.fields.material,
            "technique": draft.fields.technique,
            "dimensions": draft.fields.dimensions,
            "quantity_available": draft.fields.quantity_available,
            "production_time_days": draft.fields.production_time_days,
        }
        fields.extend(
            name
            for name, value in required.items()
            if value is None or (isinstance(value, str) and not value.strip())
        )
        primary = next((image for image in draft.images if image.is_primary), None)
        if primary is None:
            fields.append("primary_image")
        elif primary.selected_variant is None:
            fields.append("selected_image_variant")
        listing = draft.listing
        for name in ("title_hi", "title_en", "description_hi", "description_en"):
            value = getattr(listing, name) if listing is not None else None
            if not value or not value.strip():
                fields.append(name)
        if draft.pricing is None:
            fields.append("pricing")
        elif draft.pricing.draft_version != draft.version:
            fields.append("current_pricing")
        active_operations = session.scalars(
            select(Operation).where(
                Operation.owner_id == owner_id,
                Operation.resource_id == draft.id,
                Operation.status.in_(("queued", "running")),
            )
        )
        selected_image_id = primary.id if primary is not None else None
        blocks_approval = any(
            operation.type == "generate_listing"
            or (
                operation.type == "enhance_image"
                and operation.internal_payload.get("image_id") == selected_image_id
            )
            for operation in active_operations
        )
        if blocks_approval:
            fields.append("active_operation")
        return fields

    @staticmethod
    def _owned_draft_row(session: Session, owner_id: str, draft_id: str) -> CatalogDraft:
        row = session.scalar(
            select(CatalogDraft)
            .where(CatalogDraft.id == draft_id, CatalogDraft.owner_id == owner_id)
            .with_for_update()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "The draft was not found.")
        return row

    @staticmethod
    def _approval_replay(
        session: Session, owner_id: str, idempotency_key: str
    ) -> ApprovalIdempotency | None:
        return session.scalar(
            select(ApprovalIdempotency).where(
                ApprovalIdempotency.owner_id == owner_id,
                ApprovalIdempotency.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def _enquiry_replay(
        session: Session, public_share_id: str, idempotency_key: str
    ) -> EnquiryIdempotency | None:
        return session.scalar(
            select(EnquiryIdempotency).where(
                EnquiryIdempotency.public_share_id == public_share_id,
                EnquiryIdempotency.idempotency_key == idempotency_key,
            )
        )

    @staticmethod
    def _assert_same_request(stored: dict[str, object], request_payload: dict[str, object]) -> None:
        if stored != request_payload:
            raise SharingService._idempotency_conflict()

    def _approval_replay_after_race(
        self,
        owner_id: str,
        idempotency_key: str,
        request_payload: dict[str, object],
        now: datetime,
    ) -> ApprovedCatalog:
        with self.database.session() as session:
            replay = self._approval_replay(session, owner_id, idempotency_key)
            if replay is not None and ensure_utc(replay.expires_at) > now:
                self._assert_same_request(replay.request_payload, request_payload)
                return ApprovedCatalog.model_validate(replay.response_payload)
        raise self._idempotency_conflict()

    def _enquiry_replay_after_race(
        self,
        public_share_id: str,
        idempotency_key: str,
        request_payload: dict[str, object],
        now: datetime,
    ) -> EnquiryResponse:
        with self.database.session() as session:
            replay = self._enquiry_replay(session, public_share_id, idempotency_key)
            if replay is not None and ensure_utc(replay.expires_at) > now:
                self._assert_same_request(replay.request_payload, request_payload)
                return EnquiryResponse.model_validate(replay.response_payload)
        raise self._idempotency_conflict()

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
def get_sharing_service() -> SharingService:
    return SharingService(get_settings(), get_database(), get_media_storage())
