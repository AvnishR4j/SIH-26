from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

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
    otp_response = client.post(
        "/api/v1/auth/request-otp",
        headers={"Idempotency-Key": str(uuid4())},
        json={"phone": phone},
    )
    assert otp_response.status_code == 202
    token_response = client.post(
        "/api/v1/auth/verify-otp",
        json={"request_id": otp_response.json()["request_id"], "otp": "123456"},
    )
    assert token_response.status_code == 200
    return {"Authorization": f"Bearer {token_response.json()['access_token']}"}


def create_draft(
    headers: dict[str, str],
    *,
    key: str | None = None,
    craft_category: str = "textile",
) -> dict[str, Any]:
    response = client.post(
        "/api/v1/catalog/drafts",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        json={
            "craft_category": craft_category,
            "source_language": "hi",
            "initial_notes": "Hand embroidered cotton dupatta",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_draft_matches_canonical_contract_and_replays() -> None:
    headers = login_headers()
    key = str(uuid4())
    first = create_draft(headers, key=key)
    second = create_draft(headers, key=key)

    assert first == second
    assert first["id"].startswith("draft_")
    assert first["version"] == 1
    assert first["status"] == "draft"
    assert first["fields"]["product_type"] is None
    assert first["listing"] is None
    assert first["images"] == []
    assert first["voice_notes"] == []
    assert first["field_confidence"] == {}
    assert first["missing_fields"] == []
    assert first["pricing"] is None


def test_create_draft_rejects_idempotency_key_reuse_with_different_body() -> None:
    headers = login_headers()
    key = str(uuid4())
    create_draft(headers, key=key)

    response = client.post(
        "/api/v1/catalog/drafts",
        headers={**headers, "Idempotency-Key": key},
        json={"craft_category": "pottery", "source_language": "hi"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_create_draft_replay_returns_the_original_response_snapshot() -> None:
    headers = login_headers()
    key = str(uuid4())
    original = create_draft(headers, key=key)
    updated = client.patch(
        f"/api/v1/catalog/drafts/{original['id']}",
        headers=headers,
        json={"version": 1, "fields": {"material": "cotton"}},
    )
    replay = client.post(
        "/api/v1/catalog/drafts",
        headers={**headers, "Idempotency-Key": key},
        json={
            "craft_category": "textile",
            "source_language": "hi",
            "initial_notes": "Hand embroidered cotton dupatta",
        },
    )

    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert replay.status_code == 201
    assert replay.json() == original


def test_create_draft_requires_auth_and_uuid_idempotency_key() -> None:
    missing_auth = client.post(
        "/api/v1/catalog/drafts",
        headers={"Idempotency-Key": str(uuid4())},
        json={"craft_category": "textile", "source_language": "hi"},
    )
    headers = login_headers()
    invalid_key = client.post(
        "/api/v1/catalog/drafts",
        headers={**headers, "Idempotency-Key": "not-a-uuid"},
        json={"craft_category": "textile", "source_language": "hi"},
    )

    assert missing_auth.status_code == 401
    assert missing_auth.json()["error"]["code"] == "UNAUTHORIZED"
    assert invalid_key.status_code == 422
    assert invalid_key.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_drafts_paginates_and_returns_nullable_summary_fields() -> None:
    headers = login_headers()
    create_draft(headers, craft_category="textile")
    create_draft(headers, craft_category="pottery")
    create_draft(headers, craft_category="jewellery")

    first_page = client.get("/api/v1/catalog/drafts?limit=2", headers=headers)
    assert first_page.status_code == 200
    assert len(first_page.json()["items"]) == 2
    assert first_page.json()["next_cursor"] is not None
    assert first_page.json()["items"][0]["title_en"] is None
    assert first_page.json()["items"][0]["thumbnail_url"] is None
    assert first_page.json()["items"][0]["recommended_price_paise"] is None

    second_page = client.get(
        "/api/v1/catalog/drafts",
        headers=headers,
        params={"limit": 2, "cursor": first_page.json()["next_cursor"]},
    )
    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 1
    assert second_page.json()["next_cursor"] is None


def test_get_draft_does_not_reveal_another_users_resource() -> None:
    owner_headers = login_headers("+919999999999")
    draft = create_draft(owner_headers)
    other_headers = login_headers("+918888888888")

    response = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=other_headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_patch_draft_updates_only_supplied_nested_fields() -> None:
    headers = login_headers()
    draft = create_draft(headers)

    response = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={
            "version": 1,
            "fields": {"quantity_available": 2, "dimensions": "2.4 m x 1 m"},
            "listing": {"title_en": "Hand Embroidered Cotton Dupatta"},
        },
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["version"] == 2
    assert updated["fields"]["quantity_available"] == 2
    assert updated["fields"]["dimensions"] == "2.4 m x 1 m"
    assert updated["fields"]["material"] is None
    assert updated["listing"]["title_en"] == "Hand Embroidered Cotton Dupatta"
    assert updated["listing"]["title_hi"] is None

    stored = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers)
    assert stored.json() == updated


def test_patch_draft_rejects_stale_version_and_invalid_values() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    first_update = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 1, "fields": {"material": "cotton"}},
    )
    stale_update = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 1, "fields": {"quantity_available": 2}},
    )
    invalid_value = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 2, "fields": {"quantity_available": 0}},
    )

    assert first_update.status_code == 200
    assert stale_update.status_code == 409
    assert stale_update.json()["error"]["code"] == "VERSION_CONFLICT"
    assert stale_update.json()["error"]["details"]["current_version"] == 2
    assert invalid_value.status_code == 422
    assert invalid_value.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_draft_rejects_empty_changes_and_null_tags() -> None:
    headers = login_headers()
    draft = create_draft(headers)

    empty_change = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 1, "fields": {}},
    )
    null_tags = client.patch(
        f"/api/v1/catalog/drafts/{draft['id']}",
        headers=headers,
        json={"version": 1, "listing": {"tags": None}},
    )

    assert empty_change.status_code == 422
    assert null_tags.status_code == 422


def test_list_rejects_invalid_cursor_and_status() -> None:
    headers = login_headers()
    bad_cursor = client.get("/api/v1/catalog/drafts", headers=headers, params={"cursor": "broken"})
    bad_status = client.get("/api/v1/catalog/drafts", headers=headers, params={"status": "unknown"})

    assert bad_cursor.status_code == 422
    assert bad_cursor.json()["error"]["code"] == "VALIDATION_ERROR"
    assert bad_status.status_code == 422
    assert bad_status.json()["error"]["code"] == "VALIDATION_ERROR"
