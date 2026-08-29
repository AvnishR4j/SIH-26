from collections.abc import Iterator
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth import get_auth_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_auth_service() -> Iterator[None]:
    get_auth_service().reset()
    yield
    get_auth_service().reset()


def request_otp(phone: str = "+919999999999", key: str | None = None) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/request-otp",
        headers={"Idempotency-Key": key or str(uuid4())},
        json={"phone": phone},
    )
    assert response.status_code == 202
    return response.json()


def login_headers(phone: str = "+919999999999") -> dict[str, str]:
    otp = request_otp(phone)
    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"request_id": otp["request_id"], "otp": "123456"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_request_otp_matches_contract_and_replays_same_key() -> None:
    key = str(uuid4())
    first = request_otp(key=key)
    second = request_otp(key=key)

    assert first == second
    assert first["expires_in_seconds"] == 300
    assert first["retry_after_seconds"] == 30
    assert first["request_id"].startswith("otp_req_")


def test_invalid_phone_uses_standard_error_envelope() -> None:
    response = client.post(
        "/api/v1/auth/request-otp",
        headers={"Idempotency-Key": str(uuid4())},
        json={"phone": "9999999999"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "phone" in response.json()["error"]["details"]["fields"]
    assert response.json()["error"]["request_id"].startswith("req_")


def test_verify_otp_returns_bearer_token_and_user() -> None:
    otp = request_otp()
    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"request_id": otp["request_id"], "otp": "123456"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in_seconds"] == 86400
    assert body["user"]["phone"] == "+919999999999"
    assert body["user"]["role"] == "artisan"


def test_invalid_otp_is_unauthorized() -> None:
    otp = request_otp()
    response = client.post(
        "/api/v1/auth/verify-otp",
        json={"request_id": otp["request_id"], "otp": "000000"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_profile_requires_bearer_token() -> None:
    response = client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_profile_can_be_read_and_updated_without_role_escalation() -> None:
    headers = login_headers()
    response = client.patch(
        "/api/v1/me",
        headers=headers,
        json={
            "name": "Sita Devi",
            "preferred_language": "hi",
            "cluster": "Lucknow Chikankari SHG",
            "craft_categories": ["textile", "embroidery"],
        },
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Sita Devi"
    assert response.json()["role"] == "artisan"
    assert response.json()["craft_categories"] == ["textile", "embroidery"]
    assert client.get("/api/v1/me", headers=headers).json() == response.json()

    forbidden_field = client.patch(
        "/api/v1/me",
        headers=headers,
        json={"role": "admin"},
    )
    assert forbidden_field.status_code == 422
    assert forbidden_field.json()["error"]["code"] == "VALIDATION_ERROR"


def test_media_consent_requires_current_policy_version() -> None:
    headers = login_headers()
    stale = client.put(
        "/api/v1/me/consents/media-processing",
        headers=headers,
        json={"accepted": True, "policy_version": "old"},
    )
    accepted = client.put(
        "/api/v1/me/consents/media-processing",
        headers=headers,
        json={"accepted": True, "policy_version": "2026-08-29"},
    )

    assert stale.status_code == 422
    assert stale.json()["error"]["code"] == "VALIDATION_ERROR"
    assert accepted.status_code == 200
    assert accepted.json()["media_processing_accepted"] is True
    assert accepted.json()["media_processing_accepted_at"] is not None
