from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import CatalogDraft
from app.db.session import get_database
from app.main import app
from app.services.auth import get_auth_service
from app.services.catalog import get_catalog_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_services() -> Iterator[None]:
    get_auth_service().reset()
    get_catalog_service().reset()
    yield
    get_auth_service().reset()
    get_catalog_service().reset()


def login_headers(phone: str = "+919999999999") -> dict[str, str]:
    otp = client.post(
        "/api/v1/auth/request-otp",
        headers={"Idempotency-Key": str(uuid4())},
        json={"phone": phone},
    )
    assert otp.status_code == 202
    login = client.post(
        "/api/v1/auth/verify-otp",
        json={"request_id": otp.json()["request_id"], "otp": "123456"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def create_draft(headers: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/catalog/drafts",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"craft_category": "textile", "source_language": "hi"},
    )
    assert response.status_code == 201
    return response.json()


def pricing_payload(version: int = 1, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": version,
        "material_cost_paise": 30_000,
        "labour_hours": 8.0,
        "hourly_rate_paise": 5_000,
        "packaging_cost_paise": 5_000,
        "logistics_buffer_paise": 0,
        "benchmark_category": "cotton_dupatta",
    }
    payload.update(overrides)
    return payload


def suggest(
    headers: dict[str, str],
    draft_id: str,
    payload: dict[str, object],
    *,
    key: str | None = None,
):
    return client.post(
        f"/api/v1/catalog/drafts/{draft_id}/pricing/suggest",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        json=payload,
    )


def test_pricing_matches_contract_example_and_is_stored() -> None:
    headers = login_headers()
    draft = create_draft(headers)

    response = suggest(headers, draft["id"], pricing_payload())

    assert response.status_code == 200
    result = response.json()
    assert result["draft_id"] == draft["id"]
    assert result["draft_version"] == 2
    assert result["suggested_min_paise"] == 85_000
    assert result["suggested_max_paise"] == 120_000
    assert result["recommended_paise"] == 95_000
    assert result["confidence"] == "medium"
    assert result["breakdown"] == {
        "material_cost_paise": 30_000,
        "labour_cost_paise": 40_000,
        "packaging_cost_paise": 5_000,
        "logistics_buffer_paise": 0,
        "minimum_sustainable_price_paise": 75_000,
        "market_reference_low_paise": 80_000,
        "market_reference_high_paise": 140_000,
    }
    assert result["benchmark_source_label"] == "Demo benchmark dataset"
    assert result["benchmark_source_date"] == "2026-08-29"
    assert result["is_demo_data"] is True
    assert any("demo benchmark" in reason for reason in result["reasons"])

    stored = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["version"] == 2
    assert stored.json()["pricing"] == result


def test_pricing_replay_is_original_snapshot_and_does_not_increment_twice() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    key = str(uuid4())

    first = suggest(headers, draft["id"], pricing_payload(), key=key)
    replay = suggest(headers, draft["id"], pricing_payload(), key=key)
    stored = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers)

    assert first.status_code == replay.status_code == 200
    assert replay.json() == first.json()
    assert stored.json()["version"] == 2


def test_concurrent_pricing_retries_create_only_one_draft_version() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    key = str(uuid4())
    barrier = Barrier(6)

    def retry() -> tuple[int, dict[str, Any]]:
        barrier.wait()
        response = suggest(headers, draft["id"], pricing_payload(), key=key)
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: retry(), range(6)))

    assert {status for status, _ in results} == {200}
    assert len({result["draft_version"] for _, result in results}) == 1
    stored = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers)
    assert stored.json()["version"] == 2


def test_pricing_rejects_reused_key_stale_version_and_unknown_category() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    key = str(uuid4())
    assert suggest(headers, draft["id"], pricing_payload(), key=key).status_code == 200

    changed = suggest(
        headers,
        draft["id"],
        pricing_payload(material_cost_paise=31_000),
        key=key,
    )
    stale = suggest(headers, draft["id"], pricing_payload())
    unknown = suggest(
        headers,
        draft["id"],
        pricing_payload(version=2, benchmark_category="not_a_category"),
    )

    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "VERSION_CONFLICT"
    assert stale.json()["error"]["details"]["current_version"] == 2
    assert unknown.status_code == 422
    assert unknown.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "cotton_dupatta" in unknown.json()["error"]["details"]["available_categories"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("material_cost_paise", -1),
        ("labour_hours", 0),
        ("labour_hours", 10_001),
        ("hourly_rate_paise", -1),
        ("packaging_cost_paise", -1),
        ("logistics_buffer_paise", -1),
        ("benchmark_category", "   "),
    ],
)
def test_pricing_rejects_invalid_inputs(field: str, value: object) -> None:
    headers = login_headers()
    draft = create_draft(headers)

    response = suggest(headers, draft["id"], pricing_payload(**{field: value}))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_zero_direct_cost_stays_inside_benchmark_and_reports_low_confidence() -> None:
    headers = login_headers()
    draft = create_draft(headers)

    response = suggest(
        headers,
        draft["id"],
        pricing_payload(
            material_cost_paise=0,
            labour_hours=1,
            hourly_rate_paise=0,
            packaging_cost_paise=0,
            logistics_buffer_paise=0,
            benchmark_category="handmade_pottery",
        ),
    )

    assert response.status_code == 200
    result = response.json()
    assert result["suggested_min_paise"] == 50_000
    assert result["suggested_max_paise"] == 180_000
    assert result["recommended_paise"] == 115_000
    assert result["confidence"] == "low"


def test_pricing_does_not_reveal_another_users_draft() -> None:
    owner_headers = login_headers()
    draft = create_draft(owner_headers)
    other_headers = login_headers("+918888888888")

    response = suggest(other_headers, draft["id"], pricing_payload())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_edit_after_pricing_makes_the_suggestion_stale() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    priced = suggest(headers, draft["id"], pricing_payload())
    assert priced.status_code == 200

    updated = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 2, "fields": {"material": "cotton"}},
    )

    assert updated.status_code == 200
    assert updated.json()["version"] == 3
    assert updated.json()["pricing"]["draft_version"] == 2


def test_complete_draft_becomes_ready_then_edit_demotes_it() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    database = get_database()
    with database.session() as session, session.begin():
        row = session.scalar(select(CatalogDraft).where(CatalogDraft.id == draft["id"]))
        assert row is not None
        payload = dict(row.payload)
        payload["fields"] = {
            **payload["fields"],
            "product_type": "dupatta",
            "material": "cotton",
            "technique": "hand embroidery",
            "dimensions": "2.4 m x 1 m",
            "quantity_available": 2,
            "production_time_days": 7,
        }
        payload["listing"] = {
            "title_hi": "हाथ की कढ़ाई वाला दुपट्टा",
            "title_en": "Hand Embroidered Dupatta",
            "description_hi": "सूती कपड़े पर हाथ की कढ़ाई।",
            "description_en": "Hand embroidery on cotton fabric.",
            "tags": ["cotton", "handmade"],
        }
        payload["images"] = [
            {
                "id": "img_ready",
                "original_url": "http://testserver/media/original.jpg",
                "enhanced_url": None,
                "is_primary": True,
                "selected_variant": "original",
                "enhancement_status": "not_started",
                "created_at": payload["created_at"],
            }
        ]
        row.payload = payload

    priced = suggest(headers, draft["id"], pricing_payload())
    assert priced.status_code == 200
    ready = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers)
    assert ready.json()["status"] == "ready_for_approval"

    edited = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 2, "fields": {"material": "organic cotton"}},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "needs_confirmation"
    assert edited.json()["pricing"]["draft_version"] == 2
    assert edited.json()["version"] == 3


def test_openapi_exposes_pricing_contract_and_uuid_header() -> None:
    operation = app.openapi()["paths"]["/api/v1/catalog/drafts/{draft_id}/pricing/suggest"]["post"]

    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PricingSuggestion"
    }
    idempotency_header = next(
        parameter for parameter in operation["parameters"] if parameter["name"] == "Idempotency-Key"
    )
    assert idempotency_header["required"] is True
    assert idempotency_header["schema"]["format"] == "uuid"
