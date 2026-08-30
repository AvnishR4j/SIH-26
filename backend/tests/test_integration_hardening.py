from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.errors import ApiError
from app.db.models import CatalogDraft, OtpRequest
from app.main import app
from app.schemas.catalog import DraftCreate, DraftPatch, ProductFieldsUpdate
from app.services.auth import AuthService
from app.services.catalog import CatalogService

client = TestClient(app)


def settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)


def test_openapi_documents_runtime_error_envelope() -> None:
    specification = app.openapi()
    operations = [
        specification["paths"]["/api/v1/auth/request-otp"]["post"],
        specification["paths"]["/api/v1/auth/verify-otp"]["post"],
        specification["paths"]["/api/v1/me"]["patch"],
        specification["paths"]["/api/v1/catalog/drafts"]["post"],
        specification["paths"]["/api/v1/catalog/drafts/{draft_id}"]["patch"],
    ]

    for operation in operations:
        validation_schema = operation["responses"]["422"]["content"]["application/json"]["schema"]
        assert validation_schema == {"$ref": "#/components/schemas/ErrorResponse"}


def test_openapi_marks_canonical_nested_response_keys_required() -> None:
    schemas = app.openapi()["components"]["schemas"]

    assert set(schemas["ProductFields"]["required"]) == set(schemas["ProductFields"]["properties"])
    assert set(schemas["Listing"]["required"]) == set(schemas["Listing"]["properties"])


def test_json_responses_declare_utf8_and_cors_preflight_supports_frontend_headers() -> None:
    health = client.get("/api/v1/health")
    preflight = client.options(
        "/api/v1/catalog/drafts",
        headers={
            "Origin": "http://localhost:8080",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,idempotency-key,content-type",
        },
    )

    assert health.headers["content-type"] == "application/json; charset=utf-8"
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:8080"


def test_production_rejects_development_otp_and_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="DEV_OTP must be unset"):
        settings(environment="production", jwt_secret="x" * 32, dev_otp="123456")
    with pytest.raises(ValidationError, match="at least 32 characters"):
        settings(environment="production", jwt_secret="too-short", dev_otp=None)


def test_expired_access_token_is_rejected() -> None:
    service = AuthService(settings(environment="test", jwt_secret="x" * 32))
    otp = service.request_otp("+919999999999", str(uuid4()))
    login = service.verify_otp(otp.request_id, "123456")
    user_id = login.user.id
    expired_token = jwt.encode(
        {"sub": user_id, "exp": datetime.now(UTC) - timedelta(seconds=1)},
        service.settings.jwt_secret,
        algorithm=service.settings.jwt_algorithm,
    )

    with pytest.raises(ApiError) as error:
        service.authenticate(expired_token)
    assert error.value.code == "UNAUTHORIZED"


def test_otp_rate_limit_and_retry_are_atomic() -> None:
    service = AuthService(
        settings(
            environment="development",
            jwt_secret="x" * 32,
            otp_max_requests_per_15_minutes=2,
        )
    )
    replay_key = str(uuid4())
    barrier = Barrier(8)

    def request_same_otp() -> str:
        barrier.wait()
        return service.request_otp("+919999999999", replay_key).request_id

    with ThreadPoolExecutor(max_workers=8) as executor:
        request_ids = list(executor.map(lambda _: request_same_otp(), range(8)))

    assert len(set(request_ids)) == 1
    with service.database.session() as session:
        assert session.scalar(select(func.count(OtpRequest.id))) == 1
    service.request_otp("+919999999999", str(uuid4()))
    with pytest.raises(ApiError) as error:
        service.request_otp("+919999999999", str(uuid4()))
    assert error.value.code == "RATE_LIMITED"


def test_catalogue_retry_and_version_update_are_atomic() -> None:
    service = CatalogService(settings(environment="test"))
    auth_service = AuthService(settings(environment="test"))
    otp = auth_service.request_otp("+919999999999", str(uuid4()))
    login = auth_service.verify_otp(otp.request_id, "123456")
    user = auth_service.authenticate(login.access_token)
    create = DraftCreate(craft_category="textile", source_language="hi")
    replay_key = str(uuid4())
    create_barrier = Barrier(8)

    def create_same_draft() -> str:
        create_barrier.wait()
        return service.create_draft(user, create, replay_key).id

    with ThreadPoolExecutor(max_workers=8) as executor:
        draft_ids = list(executor.map(lambda _: create_same_draft(), range(8)))

    assert len(set(draft_ids)) == 1
    with service.database.session() as session:
        assert session.scalar(select(func.count(CatalogDraft.id))) == 1

    draft_id = draft_ids[0]
    patch = DraftPatch(version=1, fields=ProductFieldsUpdate(material="cotton"))
    update_barrier = Barrier(2)

    def update_same_version() -> int | str:
        update_barrier.wait()
        try:
            return service.update_draft(user, draft_id, patch).version
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: update_same_version(), range(2)))

    assert sorted(results, key=str) == [2, "VERSION_CONFLICT"]
