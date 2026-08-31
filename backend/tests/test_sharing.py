from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import BuyerEnquiry, CatalogSnapshot, Operation
from app.db.session import get_database
from app.main import app
from app.services.auth import get_auth_service
from app.services.catalog import get_catalog_service
from app.services.sharing import get_sharing_service

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


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (96, 64), (120, 45, 25)).save(output, format="JPEG")
    return output.getvalue()


def create_draft(headers: dict[str, str]) -> dict[str, Any]:
    response = client.post(
        "/api/v1/catalog/drafts",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"craft_category": "textile", "source_language": "hi"},
    )
    assert response.status_code == 201
    return response.json()


def prepare_ready_draft(headers: dict[str, str]) -> dict[str, Any]:
    profile = client.patch(
        "/api/v1/me",
        headers=headers,
        json={"name": "Sita Devi", "cluster": "Lucknow Chikankari SHG"},
    )
    assert profile.status_code == 200
    draft = create_draft(headers)
    draft_id = draft["id"]
    details = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}",
        headers=headers,
        json={
            "version": 1,
            "fields": {
                "product_type": "dupatta",
                "material": "cotton",
                "technique": "hand embroidery",
                "dimensions": "2.4 m x 1 m",
                "quantity_available": 2,
                "production_time_days": 7,
            },
            "listing": {
                "title_hi": "हाथ की कढ़ाई वाला दुपट्टा",
                "title_en": "Hand Embroidered Cotton Dupatta",
                "description_hi": "सूती कपड़े पर हाथ की कढ़ाई।",
                "description_en": "Hand embroidery on cotton fabric.",
                "tags": ["cotton", "handmade"],
            },
        },
    )
    assert details.status_code == 200
    image = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        files={"image": ("product.jpg", image_bytes(), "image/jpeg")},
    )
    assert image.status_code == 201
    selected = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image.json()['id']}",
        headers=headers,
        json={"version": 2, "selected_variant": "original"},
    )
    assert selected.status_code == 200
    priced = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/pricing/suggest",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "version": 3,
            "material_cost_paise": 30_000,
            "labour_hours": 8,
            "hourly_rate_paise": 5_000,
            "packaging_cost_paise": 5_000,
            "logistics_buffer_paise": 0,
            "benchmark_category": "cotton_dupatta",
        },
    )
    assert priced.status_code == 200
    result = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers)
    assert result.status_code == 200
    assert result.json()["version"] == 4
    assert result.json()["status"] == "ready_for_approval"
    return result.json()


def approve(
    headers: dict[str, str],
    draft_id: str,
    *,
    key: str | None = None,
    version: int = 4,
    price: int = 95_000,
    reason: str | None = None,
):
    return client.post(
        f"/api/v1/catalog/drafts/{draft_id}/approve",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        json={
            "version": version,
            "approved_price_paise": price,
            "price_override_reason": reason,
            "approval_note": "Artisan confirmed the listing and price.",
        },
    )


def enquiry_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "buyer_name": "Aarav Retail",
        "buyer_phone": "+918888888888",
        "message": "Interested in 20 pieces",
        "quantity_requested": 20,
        "consent_to_contact": True,
    }
    payload.update(overrides)
    return payload


def submit_enquiry(
    public_share_id: str,
    payload: dict[str, object],
    *,
    key: str | None = None,
):
    return client.post(
        f"/api/v1/share/{public_share_id}/enquiries",
        headers={"Idempotency-Key": key or str(uuid4())},
        json=payload,
    )


def test_approval_creates_immutable_snapshot_and_public_safe_card() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)

    response = approve(headers, draft["id"])

    assert response.status_code == 201
    approved = response.json()
    assert approved["id"].startswith("cat_")
    assert approved["draft_id"] == draft["id"]
    assert approved["status"] == "approved"
    assert approved["approved_price_paise"] == 95_000
    assert approved["currency"] == "INR"
    assert approved["public_share_id"].startswith("share_")
    assert approved["public_share_url"] == (
        f"http://localhost:3000/share/{approved['public_share_id']}"
    )

    stored_draft = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers).json()
    assert stored_draft["status"] == "approved"
    assert stored_draft["version"] == 5

    public = client.get(f"/api/v1/share/{approved['public_share_id']}")
    assert public.status_code == 200
    card = public.json()
    assert card == {
        "catalog_id": approved["id"],
        "title": "Hand Embroidered Cotton Dupatta",
        "description": "Hand embroidery on cotton fabric.",
        "image_url": (f"http://testserver/media/public/{approved['public_share_id']}/product.jpg"),
        "price_paise": 95_000,
        "currency": "INR",
        "quantity_available": 2,
        "artisan": {
            "display_name": "Sita Devi",
            "cluster": "Lucknow Chikankari SHG",
        },
        "enquiry_enabled": True,
        "published_at": approved["created_at"],
    }
    public_image = client.get(card["image_url"].removeprefix("http://testserver"))
    assert public_image.status_code == 200
    assert public_image.content == image_bytes()
    serialized = str(card).lower()
    for forbidden in (
        "+919999999999",
        "draft_",
        "img_",
        "material_cost",
        "minimum_sustainable",
        "confidence",
        "original_key",
        "voice_",
    ):
        assert forbidden not in serialized

    mutation = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 5, "fields": {"material": "silk"}},
    )
    assert mutation.status_code == 400
    assert mutation.json()["error"]["code"] == "INVALID_STATE"
    assert client.get(f"/api/v1/share/{approved['public_share_id']}").json() == card


def test_owner_can_reopen_published_catalogue_but_other_users_cannot() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    approved = approve(headers, draft["id"]).json()

    reopened = client.get(
        f"/api/v1/catalog/drafts/{draft['id']}/published",
        headers=headers,
    )

    assert reopened.status_code == 200
    assert reopened.json() == approved

    other_headers = login_headers("+918888888888")
    forbidden = client.get(
        f"/api/v1/catalog/drafts/{draft['id']}/published",
        headers=other_headers,
    )
    assert forbidden.status_code == 404
    assert forbidden.json()["error"]["code"] == "NOT_FOUND"


def test_approval_replay_is_stable_and_changed_request_conflicts() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    key = str(uuid4())

    first = approve(headers, draft["id"], key=key)
    replay = approve(headers, draft["id"], key=key)
    changed = approve(headers, draft["id"], key=key, price=96_000)

    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    with get_database().session() as session:
        assert session.scalar(select(func.count(CatalogSnapshot.id))) == 1


def test_concurrent_approval_retries_create_one_snapshot() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    key = str(uuid4())
    barrier = Barrier(5)

    def retry() -> tuple[int, dict[str, Any]]:
        barrier.wait()
        response = approve(headers, draft["id"], key=key)
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda _: retry(), range(5)))

    assert {status for status, _ in results} == {201}
    assert len({body["id"] for _, body in results}) == 1
    with get_database().session() as session:
        assert session.scalar(select(func.count(CatalogSnapshot.id))) == 1


def test_approval_reports_readiness_version_owner_and_override_errors() -> None:
    headers = login_headers()
    incomplete = create_draft(headers)
    missing = approve(headers, incomplete["id"], version=1)
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "INVALID_STATE"
    assert {
        "product_type",
        "primary_image",
        "title_hi",
        "pricing",
    }.issubset(set(missing.json()["error"]["details"]["fields"]))

    ready = prepare_ready_draft(headers)
    stale = approve(headers, ready["id"], version=3)
    assert stale.status_code == 409
    assert stale.json()["error"]["details"]["current_version"] == 4

    other_headers = login_headers("+917777777777")
    private = approve(other_headers, ready["id"])
    assert private.status_code == 404

    no_reason = approve(headers, ready["id"], price=150_000)
    assert no_reason.status_code == 422
    assert "price_override_reason" in no_reason.json()["error"]["details"]["fields"]
    with_reason = approve(
        headers,
        ready["id"],
        price=150_000,
        reason="A confirmed custom-order premium applies.",
    )
    assert with_reason.status_code == 201
    with get_database().session() as session:
        snapshot = session.scalar(
            select(CatalogSnapshot).where(CatalogSnapshot.id == with_reason.json()["id"])
        )
        assert snapshot is not None
        assert snapshot.source_draft_version == 4
        assert snapshot.price_override_reason == "A confirmed custom-order premium applies."
        assert snapshot.approval_note == "Artisan confirmed the listing and price."


def test_approval_blocks_selected_but_not_unrelated_image_work() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    selected_image_id = draft["images"][0]["id"]
    now = datetime.now(UTC)
    with get_database().session() as session, session.begin():
        session.add(
            Operation(
                id=f"op_{uuid4().hex[:12]}",
                owner_id=get_auth_service()
                .authenticate(headers["Authorization"].removeprefix("Bearer "))
                .id,
                type="enhance_image",
                status="queued",
                resource_type="draft",
                resource_id=draft["id"],
                internal_payload={"image_id": selected_image_id},
                error=None,
                created_at=now,
                updated_at=now,
            )
        )

    blocked = approve(headers, draft["id"])
    assert blocked.status_code == 400
    assert "active_operation" in blocked.json()["error"]["details"]["fields"]

    with get_database().session() as session, session.begin():
        operation = session.scalar(select(Operation).where(Operation.resource_id == draft["id"]))
        assert operation is not None
        operation.internal_payload = {"image_id": "img_unrelated"}
    allowed = approve(headers, draft["id"])
    assert allowed.status_code == 201


def test_public_enquiry_is_idempotent_private_and_persisted() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    approved = approve(headers, draft["id"]).json()
    key = str(uuid4())

    first = submit_enquiry(approved["public_share_id"], enquiry_payload(), key=key)
    replay = submit_enquiry(approved["public_share_id"], enquiry_payload(), key=key)
    changed = submit_enquiry(
        approved["public_share_id"],
        enquiry_payload(message="A different message"),
        key=key,
    )

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert first.json()["enquiry_id"].startswith("enq_")
    assert first.json()["status"] == "received"
    assert changed.status_code == 409
    with get_database().session() as session:
        enquiries = list(session.scalars(select(BuyerEnquiry)))
    assert len(enquiries) == 1
    assert enquiries[0].buyer_phone == "+918888888888"
    assert enquiries[0].buyer_name == "Aarav Retail"


def test_concurrent_enquiry_retries_create_one_record() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    share_id = approve(headers, draft["id"]).json()["public_share_id"]
    key = str(uuid4())
    barrier = Barrier(6)

    def retry() -> tuple[int, dict[str, Any]]:
        barrier.wait()
        response = submit_enquiry(share_id, enquiry_payload(), key=key)
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda _: retry(), range(6)))

    assert {status for status, _ in results} == {201}
    assert len({body["enquiry_id"] for _, body in results}) == 1
    with get_database().session() as session:
        assert session.scalar(select(func.count(BuyerEnquiry.id))) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("buyer_name", "   "),
        ("buyer_phone", "8888888888"),
        ("quantity_requested", 0),
        ("consent_to_contact", False),
    ],
)
def test_enquiry_rejects_invalid_input(field: str, value: object) -> None:
    response = submit_enquiry(
        "share_unknown",
        enquiry_payload(**{field: value}),
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_enquiry_rate_limit_applies_after_replay_check() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    share_id = approve(headers, draft["id"]).json()["public_share_id"]
    limit = get_settings().enquiry_max_per_hour_per_buyer
    keys = [str(uuid4()) for _ in range(limit)]

    for key in keys:
        assert submit_enquiry(share_id, enquiry_payload(), key=key).status_code == 201
    replay = submit_enquiry(share_id, enquiry_payload(), key=keys[0])
    blocked = submit_enquiry(share_id, enquiry_payload())

    assert replay.status_code == 201
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "3600"
    assert blocked.json()["error"]["code"] == "RATE_LIMITED"


def test_enquiry_retry_rechecks_replay_after_snapshot_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    share_id = approve(headers, draft["id"]).json()["public_share_id"]
    key = str(uuid4())
    first = submit_enquiry(share_id, enquiry_payload(), key=key)
    service = get_sharing_service()
    real_replay = service._enquiry_replay
    calls = 0

    def delayed_replay(*args: object):
        nonlocal calls
        calls += 1
        return None if calls == 1 else real_replay(*args)

    monkeypatch.setattr(service, "_enquiry_replay", delayed_replay)
    retry = submit_enquiry(share_id, enquiry_payload(), key=key)

    assert retry.status_code == 201
    assert retry.json() == first.json()
    assert calls == 2


def test_unknown_public_share_is_not_found() -> None:
    read = client.get("/api/v1/share/share_unknown")
    submit = submit_enquiry("share_unknown", enquiry_payload())
    assert read.status_code == submit.status_code == 404
    assert read.json()["error"]["code"] == "NOT_FOUND"


def test_marketplace_lists_only_safe_approved_catalogues_with_pagination() -> None:
    first_headers = login_headers("+919999999991")
    first_draft = prepare_ready_draft(first_headers)
    first = approve(first_headers, first_draft["id"])
    assert first.status_code == 201

    second_headers = login_headers("+919999999992")
    second_draft = prepare_ready_draft(second_headers)
    second = approve(second_headers, second_draft["id"])
    assert second.status_code == 201

    first_page = client.get("/api/v1/marketplace/catalogues", params={"limit": 1})
    assert first_page.status_code == 200
    first_item = first_page.json()["items"][0]
    cursor = first_page.json()["next_cursor"]
    assert cursor is not None
    assert first_item["public_share_id"] in {
        first.json()["public_share_id"],
        second.json()["public_share_id"],
    }
    assert first_item["artisan"]["display_name"] == "Sita Devi"
    serialized = str(first_item).lower()
    for forbidden in ("+919", "draft_", "voice_", "material_cost", "owner_id"):
        assert forbidden not in serialized

    second_page = client.get(
        "/api/v1/marketplace/catalogues", params={"limit": 1, "cursor": cursor}
    )
    assert second_page.status_code == 200
    assert second_page.json()["items"][0]["public_share_id"] != first_item["public_share_id"]
    assert second_page.json()["next_cursor"] is None

    invalid = client.get("/api/v1/marketplace/catalogues", params={"cursor": "bad"})
    assert invalid.status_code == 422


def test_delete_hides_an_approved_catalogue_from_public_surfaces() -> None:
    headers = login_headers()
    draft = prepare_ready_draft(headers)
    approved = approve(headers, draft["id"])
    assert approved.status_code == 201
    share_id = approved.json()["public_share_id"]

    deleted = client.delete(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers)

    assert deleted.status_code == 204
    assert client.get(f"/api/v1/share/{share_id}").status_code == 404
    assert submit_enquiry(share_id, enquiry_payload()).status_code == 404
    marketplace = client.get("/api/v1/marketplace/catalogues")
    assert marketplace.status_code == 200
    assert marketplace.json()["items"] == []


def test_openapi_documents_approval_share_and_enquiry_contracts() -> None:
    paths = app.openapi()["paths"]
    delete = paths["/api/v1/catalog/drafts/{draft_id}"]["delete"]
    approval = paths["/api/v1/catalog/drafts/{draft_id}/approve"]["post"]
    share = paths["/api/v1/share/{public_share_id}"]["get"]
    enquiry = paths["/api/v1/share/{public_share_id}/enquiries"]["post"]

    assert approval["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApprovedCatalog"
    }
    assert share["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/PublicShareCard"
    }
    assert enquiry["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/EnquiryResponse"
    }
    assert delete["responses"]["204"]["description"] == "Successful Response"
