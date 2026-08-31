from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ApiError
from app.db.base import ensure_utc
from app.db.models import (
    CatalogDraft,
    Operation,
    PricingBenchmark,
    PricingSuggestionIdempotency,
)
from app.db.session import Database, get_database
from app.schemas.catalog import (
    Draft,
    PricingBreakdown,
    PricingSuggestion,
    PricingSuggestionRequest,
)
from app.services.auth import UserRecord

PRICE_ROUNDING_UNIT_PAISE = 5_000


class PricingService:
    def __init__(self, settings: Settings, database: Database | None = None) -> None:
        self.settings = settings
        self.database = database or get_database()
        self._lock = self.database.write_lock

    def suggest_price(
        self,
        user: UserRecord,
        draft_id: str,
        request: PricingSuggestionRequest,
        idempotency_key: str,
    ) -> PricingSuggestion:
        now = datetime.now(UTC)
        request_payload = {"draft_id": draft_id, **request.model_dump(mode="json")}
        with self._lock:
            try:
                with self.database.session() as session, session.begin():
                    replay = self._replay(session, user.id, idempotency_key)
                    if replay is not None and ensure_utc(replay.expires_at) > now:
                        if replay.request_payload != request_payload:
                            raise self._idempotency_conflict()
                        return PricingSuggestion.model_validate(replay.response_payload)
                    if replay is not None:
                        session.delete(replay)
                        session.flush()

                    row = self._owned_draft_row(session, user.id, draft_id)
                    draft = Draft.model_validate(row.payload)
                    concurrent_replay = self._replay(session, user.id, idempotency_key)
                    if (
                        concurrent_replay is not None
                        and ensure_utc(concurrent_replay.expires_at) > now
                    ):
                        if concurrent_replay.request_payload != request_payload:
                            raise self._idempotency_conflict()
                        return PricingSuggestion.model_validate(concurrent_replay.response_payload)
                    if draft.status == "approved":
                        raise ApiError(
                            400,
                            "INVALID_STATE",
                            "An approved draft cannot be changed.",
                        )
                    if request.version != draft.version:
                        raise self._version_conflict(draft.version)
                    benchmark = session.get(PricingBenchmark, request.benchmark_category)
                    fallback_category = None
                    if benchmark is None:
                        fallback_category = request.benchmark_category
                        benchmark = session.get(PricingBenchmark, "generic_handicraft")
                        if benchmark is None:
                            raise ApiError(
                                503,
                                "CONFIGURATION_ERROR",
                                "The generic pricing benchmark is unavailable.",
                            )

                    suggestion = self._calculate(
                        draft_id,
                        draft.version + 1,
                        request,
                        benchmark,
                        fallback_category=fallback_category,
                    )
                    updated = draft.model_copy(
                        update={
                            "version": draft.version + 1,
                            "pricing": suggestion,
                            "updated_at": now,
                        }
                    )
                    if self._ready_for_approval(session, user.id, updated):
                        updated = updated.model_copy(update={"status": "ready_for_approval"})
                    row.version = updated.version
                    row.status = updated.status
                    row.payload = updated.model_dump(mode="json")
                    row.updated_at = now
                    session.add(
                        PricingSuggestionIdempotency(
                            owner_id=user.id,
                            idempotency_key=idempotency_key,
                            request_payload=request_payload,
                            response_payload=suggestion.model_dump(mode="json"),
                            draft_id=draft_id,
                            expires_at=now
                            + timedelta(seconds=self.settings.idempotency_ttl_seconds),
                            created_at=now,
                        )
                    )
                    return suggestion
            except IntegrityError:
                return self._replay_after_race(
                    user.id,
                    idempotency_key,
                    request_payload,
                    now,
                )

    @staticmethod
    def _calculate(
        draft_id: str,
        draft_version: int,
        request: PricingSuggestionRequest,
        benchmark: PricingBenchmark,
        *,
        fallback_category: str | None = None,
    ) -> PricingSuggestion:
        labour_cost = int(
            (Decimal(str(request.labour_hours)) * Decimal(request.hourly_rate_paise)).quantize(
                Decimal(1), rounding=ROUND_HALF_UP
            )
        )
        minimum = (
            request.material_cost_paise
            + labour_cost
            + request.packaging_cost_paise
            + request.logistics_buffer_paise
        )
        if minimum == 0:
            suggested_min = benchmark.low_paise
            suggested_max = benchmark.high_paise
            recommended = min(
                max(
                    PricingService._round_nearest(
                        (benchmark.low_paise + benchmark.high_paise) // 2
                    ),
                    suggested_min,
                ),
                suggested_max,
            )
            confidence = "low"
        else:
            cost_low = PricingService._round_up_ratio(minimum, 110, 100)
            cost_recommended = PricingService._round_nearest_ratio(minimum, 125, 100)
            cost_high = PricingService._round_up_ratio(minimum, 160, 100)
            suggested_min = max(cost_low, min(benchmark.low_paise, cost_recommended))
            if benchmark.high_paise >= suggested_min:
                suggested_max = min(
                    max(cost_high, benchmark.low_paise),
                    benchmark.high_paise,
                )
            else:
                suggested_max = cost_high
            suggested_max = max(suggested_min, suggested_max)
            recommended = min(
                max(cost_recommended, suggested_min),
                suggested_max,
            )
            overlaps = cost_low <= benchmark.high_paise and cost_high >= benchmark.low_paise
            confidence = "medium" if overlaps else "low"
            if overlaps and not benchmark.is_demo_data:
                confidence = "high"

        reasons = [
            "The minimum includes material, labour, packaging, and logistics costs.",
            (
                f"Labour uses {request.labour_hours:g} hours at "
                f"{request.hourly_rate_paise} paise per hour."
            ),
        ]
        if benchmark.is_demo_data:
            reasons.append(
                "The market comparison uses demo benchmark data and must be reviewed before sale."
            )
        if fallback_category is not None:
            reasons.append(
                f"No exact benchmark exists for '{fallback_category}', so a generic handicraft reference band was used."
            )
        if confidence == "low":
            reasons.append(
                "Confidence is low because the cost inputs and benchmark band do not align closely."
            )
        return PricingSuggestion(
            draft_id=draft_id,
            draft_version=draft_version,
            suggested_min_paise=suggested_min,
            suggested_max_paise=suggested_max,
            recommended_paise=recommended,
            confidence=confidence,
            breakdown=PricingBreakdown(
                material_cost_paise=request.material_cost_paise,
                labour_cost_paise=labour_cost,
                packaging_cost_paise=request.packaging_cost_paise,
                logistics_buffer_paise=request.logistics_buffer_paise,
                minimum_sustainable_price_paise=minimum,
                market_reference_low_paise=benchmark.low_paise,
                market_reference_high_paise=benchmark.high_paise,
            ),
            reasons=reasons,
            benchmark_category=benchmark.category,
            benchmark_source_label=benchmark.source_label,
            benchmark_source_date=benchmark.source_date,
            is_demo_data=benchmark.is_demo_data,
        )

    @staticmethod
    def _round_up_ratio(value: int, numerator: int, denominator: int) -> int:
        scaled = value * numerator
        unit = PRICE_ROUNDING_UNIT_PAISE * denominator
        return ((scaled + unit - 1) // unit) * PRICE_ROUNDING_UNIT_PAISE

    @staticmethod
    def _round_nearest_ratio(value: int, numerator: int, denominator: int) -> int:
        scaled = Decimal(value * numerator) / Decimal(denominator)
        return PricingService._round_nearest(int(scaled.quantize(Decimal(1))))

    @staticmethod
    def _round_nearest(value: int) -> int:
        units = (Decimal(value) / Decimal(PRICE_ROUNDING_UNIT_PAISE)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
        return int(units) * PRICE_ROUNDING_UNIT_PAISE

    @staticmethod
    def _ready_for_approval(session: Session, owner_id: str, draft: Draft) -> bool:
        fields = draft.fields
        required_values = (
            draft.craft_category,
            fields.product_type,
            fields.material,
            fields.technique,
            fields.dimensions,
            fields.quantity_available,
            fields.production_time_days,
        )
        if any(
            value is None or (isinstance(value, str) and not value.strip())
            for value in required_values
        ):
            return False
        primary = next((image for image in draft.images if image.is_primary), None)
        if primary is None or primary.selected_variant is None:
            return False
        listing = draft.listing
        if listing is None or any(
            not value or not value.strip()
            for value in (
                listing.title_hi,
                listing.title_en,
                listing.description_hi,
                listing.description_en,
            )
        ):
            return False
        if draft.pricing is None or draft.pricing.draft_version != draft.version:
            return False
        active_operation = session.scalar(
            select(Operation.id).where(
                Operation.owner_id == owner_id,
                Operation.resource_id == draft.id,
                Operation.status.in_(("queued", "running")),
            )
        )
        return active_operation is None

    @staticmethod
    def _owned_draft_row(session: Session, owner_id: str, draft_id: str) -> CatalogDraft:
        row = session.scalar(
            select(CatalogDraft)
            .where(
                CatalogDraft.id == draft_id,
                CatalogDraft.owner_id == owner_id,
            )
            .with_for_update()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "The draft was not found.")
        return row

    @staticmethod
    def _replay(
        session: Session, owner_id: str, idempotency_key: str
    ) -> PricingSuggestionIdempotency | None:
        return session.scalar(
            select(PricingSuggestionIdempotency).where(
                PricingSuggestionIdempotency.owner_id == owner_id,
                PricingSuggestionIdempotency.idempotency_key == idempotency_key,
            )
        )

    def _replay_after_race(
        self,
        owner_id: str,
        idempotency_key: str,
        request_payload: dict[str, object],
        now: datetime,
    ) -> PricingSuggestion:
        with self.database.session() as session:
            replay = self._replay(session, owner_id, idempotency_key)
            if replay is not None and ensure_utc(replay.expires_at) > now:
                if replay.request_payload != request_payload:
                    raise self._idempotency_conflict()
                return PricingSuggestion.model_validate(replay.response_payload)
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
def get_pricing_service() -> PricingService:
    return PricingService(get_settings(), get_database())
