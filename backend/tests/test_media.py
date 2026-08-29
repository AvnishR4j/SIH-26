from collections.abc import Iterator
from io import BytesIO
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.models import CatalogDraft, Operation
from app.db.session import get_database
from app.main import app
from app.schemas.catalog import ImageEnhancementRequest
from app.services.auth import UserRecord, get_auth_service
from app.services.media import MediaService, get_media_service
from app.storage.local import LocalMediaStorage, get_media_storage

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_services() -> Iterator[None]:
    get_auth_service().reset()
    yield
    get_auth_service().reset()


def image_bytes(
    image_format: str = "JPEG",
    color: tuple[int, int, int] = (180, 70, 40),
    size: tuple[int, int] = (96, 64),
) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format=image_format)
    return output.getvalue()


def login_headers(phone: str = "+919999999999") -> dict[str, str]:
    otp = client.post(
        "/api/v1/auth/request-otp",
        headers={"Idempotency-Key": str(uuid4())},
        json={"phone": phone},
    )
    token = client.post(
        "/api/v1/auth/verify-otp",
        json={"request_id": otp.json()["request_id"], "otp": "123456"},
    )
    assert token.status_code == 200
    return {"Authorization": f"Bearer {token.json()['access_token']}"}


def create_draft(headers: dict[str, str]) -> dict[str, object]:
    response = client.post(
        "/api/v1/catalog/drafts",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={"craft_category": "textile", "source_language": "hi"},
    )
    assert response.status_code == 201
    return response.json()


def upload_image(
    headers: dict[str, str],
    draft_id: str,
    content: bytes,
    *,
    key: str | None = None,
    is_primary: bool = True,
    filename: str = "product.jpg",
    content_type: str = "image/jpeg",
):
    return client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        data={"is_primary": str(is_primary).lower()},
        files={"image": (filename, content, content_type)},
    )


def accept_consent(headers: dict[str, str]) -> None:
    response = client.put(
        "/api/v1/me/consents/media-processing",
        headers=headers,
        json={"accepted": True, "policy_version": "2026-08-29"},
    )
    assert response.status_code == 200


def test_upload_validates_decoded_content_and_serves_the_preserved_original() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    png = image_bytes("PNG")

    response = upload_image(
        headers,
        str(draft["id"]),
        png,
        is_primary=False,
        filename="misleading.jpg",
        content_type="image/jpeg",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("img_")
    assert body["is_primary"] is True
    assert body["selected_variant"] is None
    assert body["enhancement_status"] == "not_started"
    assert body["original_url"].endswith(".png")

    stored_file = client.get(urlsplit(body["original_url"]).path)
    assert stored_file.status_code == 200
    assert stored_file.content == png
    with Image.open(BytesIO(stored_file.content)) as decoded:
        assert decoded.format == "PNG"

    stored_draft = client.get(f"/api/v1/catalog/drafts/{draft['id']}", headers=headers).json()
    assert stored_draft["images"] == [body]
    assert stored_draft["version"] == 1


def test_upload_rejects_invalid_and_oversized_files_with_contract_errors() -> None:
    headers = login_headers()
    draft = create_draft(headers)

    invalid = upload_image(headers, str(draft["id"]), b"not really an image")
    oversized = upload_image(
        headers,
        str(draft["id"]),
        b"x" * (10_485_760 + 1),
    )

    assert invalid.status_code == 415
    assert invalid.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert oversized.status_code == 413
    assert oversized.json()["error"]["code"] == "UPLOAD_TOO_LARGE"


def test_upload_rejects_excessive_decoded_dimensions_before_persistence() -> None:
    settings = get_settings().model_copy(update={"max_image_pixels": 100})
    service = MediaService(settings, get_database(), get_media_storage())

    with pytest.raises(ApiError) as error:
        service.upload_image(
            UserRecord(id="unused", phone="+919999999999"),
            "unused",
            image_bytes(size=(11, 10)),
            True,
            str(uuid4()),
        )

    assert error.value.status_code == 413
    assert error.value.code == "UPLOAD_TOO_LARGE"


def test_upload_retries_and_primary_selection_are_deterministic() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    first_content = image_bytes(color=(200, 20, 20))
    first_key = str(uuid4())

    first = upload_image(
        headers,
        draft_id,
        first_content,
        key=first_key,
        is_primary=False,
    )
    replay = upload_image(
        headers,
        draft_id,
        first_content,
        key=first_key,
        is_primary=False,
    )
    conflict = upload_image(
        headers,
        draft_id,
        image_bytes(color=(20, 200, 20)),
        key=first_key,
        is_primary=False,
    )
    second = upload_image(
        headers,
        draft_id,
        image_bytes(color=(20, 20, 200)),
        is_primary=False,
    )
    third = upload_image(
        headers,
        draft_id,
        image_bytes(color=(80, 80, 80)),
        is_primary=True,
    )

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert second.status_code == third.status_code == 201

    images = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()["images"]
    assert len(images) == 3
    assert sum(image["is_primary"] for image in images) == 1
    assert next(image for image in images if image["is_primary"])["id"] == third.json()["id"]


def test_enhancement_requires_consent_and_produces_pollable_operation() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    uploaded = upload_image(headers, draft_id, image_bytes()).json()
    image_id = uploaded["id"]
    enhancement_key = str(uuid4())
    request_body = {
        "background": "neutral",
        "crop_style": "marketplace_square",
        "preserve_original": True,
    }

    without_consent = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}/enhance",
        headers={**headers, "Idempotency-Key": enhancement_key},
        json=request_body,
    )
    premature_selection = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}",
        headers=headers,
        json={"version": 1, "selected_variant": "enhanced"},
    )
    assert without_consent.status_code == 403
    assert without_consent.json()["error"]["code"] == "CONSENT_REQUIRED"
    assert premature_selection.status_code == 400

    accept_consent(headers)
    started = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}/enhance",
        headers={**headers, "Idempotency-Key": enhancement_key},
        json=request_body,
    )
    assert started.status_code == 202
    assert started.json()["status"] == "queued"
    assert started.headers["location"] == f"/api/v1/operations/{started.json()['id']}"

    operation = client.get(started.headers["location"], headers=headers)
    assert operation.status_code == 200
    assert operation.json()["status"] == "succeeded"
    assert operation.json()["type"] == "enhance_image"

    updated_draft = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    enhanced_image = updated_draft["images"][0]
    assert enhanced_image["enhancement_status"] == "succeeded"
    assert enhanced_image["enhanced_url"].endswith("enhanced.jpg")
    enhanced_file = client.get(urlsplit(enhanced_image["enhanced_url"]).path)
    assert enhanced_file.status_code == 200
    with Image.open(BytesIO(enhanced_file.content)) as decoded:
        assert decoded.format == "JPEG"
        assert decoded.width == decoded.height

    selected = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}",
        headers=headers,
        json={"version": 1, "is_primary": True, "selected_variant": "enhanced"},
    )
    assert selected.status_code == 200
    assert selected.json()["version"] == 2
    assert selected.json()["images"][0]["selected_variant"] == "enhanced"

    cannot_unset = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}",
        headers=headers,
        json={"version": 2, "is_primary": False},
    )
    assert cannot_unset.status_code == 400
    assert cannot_unset.json()["error"]["code"] == "INVALID_STATE"

    replay = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}/enhance",
        headers={**headers, "Idempotency-Key": enhancement_key},
        json=request_body,
    )
    assert replay.status_code == 202
    assert replay.json() == started.json()
    changed_replay = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}/enhance",
        headers={**headers, "Idempotency-Key": enhancement_key},
        json={**request_body, "crop_style": "keep_original"},
    )
    stale_selection = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}",
        headers=headers,
        json={"version": 1, "selected_variant": "original"},
    )
    assert changed_replay.status_code == 409
    assert changed_replay.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert stale_selection.status_code == 409
    assert stale_selection.json()["error"]["code"] == "VERSION_CONFLICT"


def test_media_resources_do_not_leak_across_users() -> None:
    owner_headers = login_headers("+919999999999")
    draft = create_draft(owner_headers)
    draft_id = str(draft["id"])
    image = upload_image(owner_headers, draft_id, image_bytes()).json()
    accept_consent(owner_headers)
    operation = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image['id']}/enhance",
        headers={**owner_headers, "Idempotency-Key": str(uuid4())},
        json={},
    )
    other_headers = login_headers("+918888888888")

    upload_to_private_draft = upload_image(
        other_headers,
        draft_id,
        image_bytes(color=(1, 2, 3)),
    )
    read_private_operation = client.get(
        f"/api/v1/operations/{operation.json()['id']}", headers=other_headers
    )
    patch_private_image = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image['id']}",
        headers=other_headers,
        json={"version": 1, "selected_variant": "original"},
    )

    assert upload_to_private_draft.status_code == 404
    assert read_private_operation.status_code == 404
    assert patch_private_image.status_code == 404


def test_enhancement_failure_is_persisted_for_polling() -> None:
    class FailingReadStorage(LocalMediaStorage):
        def read(self, key: str) -> bytes:
            raise ApiError(503, "STORAGE_UNAVAILABLE", "Media storage is unavailable.")

    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    image = upload_image(headers, draft_id, image_bytes()).json()
    accept_consent(headers)
    token = headers["Authorization"].removeprefix("Bearer ")
    user = get_auth_service().authenticate(token)
    settings = get_settings()
    service = MediaService(settings, get_database(), FailingReadStorage(settings))
    operation, _ = service.start_image_enhancement(
        user,
        draft_id,
        image["id"],
        ImageEnhancementRequest(),
        str(uuid4()),
    )

    service.complete_image_enhancement(user.id, operation.id)

    failed = service.get_operation(user, operation.id)
    stored_draft = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    assert failed.status == "failed"
    assert failed.error is not None
    assert failed.error.code == "STORAGE_UNAVAILABLE"
    assert stored_draft["images"][0]["enhancement_status"] == "failed"
    assert stored_draft["last_processing_error"]["code"] == "STORAGE_UNAVAILABLE"


def test_only_queued_operation_can_claim_enhancement_work() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    image = upload_image(headers, draft_id, image_bytes()).json()
    accept_consent(headers)
    token = headers["Authorization"].removeprefix("Bearer ")
    user = get_auth_service().authenticate(token)
    service = get_media_service()
    operation, _ = service.start_image_enhancement(
        user,
        draft_id,
        image["id"],
        ImageEnhancementRequest(),
        str(uuid4()),
    )
    with get_database().session() as session, session.begin():
        stored = session.get(Operation, operation.id)
        assert stored is not None
        stored.status = "running"

    service.complete_image_enhancement(user.id, operation.id)

    still_running = service.get_operation(user, operation.id)
    stored_draft = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    assert still_running.status == "running"
    assert stored_draft["images"][0]["enhancement_status"] == "queued"


def test_approved_draft_rejects_all_image_mutations() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    image = upload_image(headers, draft_id, image_bytes()).json()
    accept_consent(headers)
    with get_database().session() as session, session.begin():
        row = session.get(CatalogDraft, draft_id)
        assert row is not None
        payload = dict(row.payload)
        payload["status"] = "approved"
        row.status = "approved"
        row.payload = payload

    upload = upload_image(headers, draft_id, image_bytes(color=(1, 1, 1)))
    enhance = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image['id']}/enhance",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={},
    )
    patch = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image['id']}",
        headers=headers,
        json={"version": 1, "selected_variant": "original"},
    )

    assert upload.status_code == 400
    assert enhance.status_code == 400
    assert patch.status_code == 400
    assert all(
        response.json()["error"]["code"] == "INVALID_STATE" for response in (upload, enhance, patch)
    )


def test_media_openapi_exposes_the_frozen_integration_surface() -> None:
    paths = app.openapi()["paths"]
    upload = paths["/api/v1/catalog/drafts/{draft_id}/images"]["post"]
    enhance = paths["/api/v1/catalog/drafts/{draft_id}/images/{image_id}/enhance"]["post"]
    patch = paths["/api/v1/catalog/drafts/{draft_id}/images/{image_id}"]["patch"]
    operation = paths["/api/v1/operations/{operation_id}"]["get"]

    assert "multipart/form-data" in upload["requestBody"]["content"]
    assert {"201", "413", "415", "422"}.issubset(upload["responses"])
    assert {"202", "403", "409", "422"}.issubset(enhance["responses"])
    assert {"200", "400", "409", "422"}.issubset(patch["responses"])
    assert {"200", "401", "404"}.issubset(operation["responses"])
