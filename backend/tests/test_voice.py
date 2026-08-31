import wave
from collections.abc import Iterator
from io import BytesIO
from math import sin, tau
from struct import pack
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.models import CatalogDraft, Operation, VoiceMedia
from app.db.session import get_database
from app.main import app
from app.schemas.catalog import GenerateListingRequest
from app.services.auth import get_auth_service
from app.services.speech import TranscriptionResult
from app.services.voice import VoiceService, get_voice_service
from app.storage.local import get_media_storage

client = TestClient(app)


class FakeTranscriber:
    def __init__(self) -> None:
        self.calls: list[tuple[bytes, str]] = []
        self.error: Exception | None = None

    def transcribe(self, content: bytes, language: str) -> TranscriptionResult:
        self.calls.append((content, language))
        if self.error is not None:
            raise self.error
        return TranscriptionResult(
            text="यह हाथ से बना हुआ कपड़े का उत्पाद है।",
            language="hi",
        )


@pytest.fixture(autouse=True)
def voice_service_override() -> Iterator[FakeTranscriber]:
    get_auth_service().reset()
    transcriber = FakeTranscriber()
    service = VoiceService(
        get_settings(),
        get_database(),
        get_media_storage(),
        transcriber,
    )
    app.dependency_overrides[get_voice_service] = lambda: service
    yield transcriber
    app.dependency_overrides.pop(get_voice_service, None)
    get_auth_service().reset()


def wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 8_000) -> bytes:
    output = BytesIO()
    sample_count = round(duration_seconds * sample_rate)
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        frames = b"".join(
            pack("<h", round(2_000 * sin(tau * 220 * index / sample_rate)))
            for index in range(sample_count)
        )
        audio.writeframes(frames)
    return output.getvalue()


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 60), (120, 40, 20)).save(output, format="JPEG")
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


def upload_image(headers: dict[str, str], draft_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        data={"is_primary": "true"},
        files={"image": ("product.jpg", image_bytes(), "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


def upload_voice(
    headers: dict[str, str],
    draft_id: str,
    content: bytes | None = None,
    *,
    key: str | None = None,
    language: str = "hi",
):
    return client.post(
        f"/api/v1/catalog/drafts/{draft_id}/voice-notes",
        headers={**headers, "Idempotency-Key": key or str(uuid4())},
        data={"language": language},
        files={"audio": ("description.wav", content or wav_bytes(), "audio/wav")},
    )


def accept_consent(headers: dict[str, str]) -> None:
    response = client.put(
        "/api/v1/me/consents/media-processing",
        headers=headers,
        json={"accepted": True, "policy_version": "2026-08-29"},
    )
    assert response.status_code == 200


def test_voice_upload_decodes_audio_persists_original_and_sets_media_ready() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    upload_image(headers, draft_id)
    content = wav_bytes(1.2)

    response = upload_voice(headers, draft_id, content)

    assert response.status_code == 201
    body = response.json()
    assert body["id"].startswith("voice_")
    assert body["language"] == "hi"
    assert body["duration_seconds"] == 2
    stored_draft = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    assert stored_draft["voice_notes"] == [body]
    assert stored_draft["status"] == "media_ready"
    with get_database().session() as session:
        media = session.get(VoiceMedia, body["id"])
        assert media is not None
        assert get_media_storage().read(media.audio_key) == content


def test_image_uploaded_after_voice_also_sets_media_ready() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    assert upload_voice(headers, draft_id).status_code == 201

    upload_image(headers, draft_id)

    stored = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    assert stored["status"] == "media_ready"


def test_additional_media_does_not_regress_post_generation_status() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    first_image = upload_image(headers, draft_id)
    first_voice = upload_voice(headers, draft_id).json()
    accept_consent(headers)
    generated = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/generate-listing",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "voice_note_id": first_voice["id"],
            "image_id": first_image["id"],
            "target_languages": ["hi", "en"],
        },
    )
    assert generated.status_code == 202

    upload_image(headers, draft_id)
    upload_voice(headers, draft_id)

    stored = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    assert stored["status"] == "needs_confirmation"


def test_voice_upload_rejects_invalid_oversized_and_overlong_audio() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    invalid = upload_voice(headers, draft_id, b"not audio")

    settings = get_settings().model_copy(
        update={"max_audio_bytes": 100, "max_audio_duration_seconds": 1}
    )
    service = VoiceService(
        settings,
        get_database(),
        get_media_storage(),
        FakeTranscriber(),
    )
    token = headers["Authorization"].removeprefix("Bearer ")
    user = get_auth_service().authenticate(token)
    with pytest.raises(ApiError) as oversized:
        service.upload_voice_note(user, draft_id, wav_bytes(), "hi", str(uuid4()))
    settings = settings.model_copy(update={"max_audio_bytes": 1_000_000})
    service = VoiceService(settings, get_database(), get_media_storage(), FakeTranscriber())
    with pytest.raises(ApiError) as overlong:
        service.upload_voice_note(user, draft_id, wav_bytes(1.2), "hi", str(uuid4()))

    assert invalid.status_code == 415
    assert invalid.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert oversized.value.status_code == 413
    assert overlong.value.status_code == 413


def test_voice_upload_replay_and_owner_isolation() -> None:
    owner_headers = login_headers()
    draft = create_draft(owner_headers)
    draft_id = str(draft["id"])
    content = wav_bytes()
    key = str(uuid4())
    first = upload_voice(owner_headers, draft_id, content, key=key)
    replay = upload_voice(owner_headers, draft_id, content, key=key)
    changed = upload_voice(owner_headers, draft_id, content, key=key, language="en")
    other_headers = login_headers("+918888888888")
    private = upload_voice(other_headers, draft_id)

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert private.status_code == 404
    stored = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=owner_headers).json()
    assert len(stored["voice_notes"]) == 1


def test_generation_requires_consent_and_stores_grounded_transcript(
    voice_service_override: FakeTranscriber,
) -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    image = upload_image(headers, draft_id)
    voice = upload_voice(headers, draft_id).json()
    request = {
        "voice_note_id": voice["id"],
        "image_id": image["id"],
        "target_languages": ["hi", "en"],
    }
    key = str(uuid4())
    without_consent = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/generate-listing",
        headers={**headers, "Idempotency-Key": key},
        json=request,
    )
    assert without_consent.status_code == 403

    accept_consent(headers)
    started = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/generate-listing",
        headers={**headers, "Idempotency-Key": key},
        json=request,
    )
    assert started.status_code == 202
    assert started.json()["status"] == "queued"
    assert started.headers["location"] == f"/api/v1/operations/{started.json()['id']}"
    operation = client.get(started.headers["location"], headers=headers)
    assert operation.status_code == 200
    assert operation.json()["status"] == "succeeded"
    assert operation.json()["type"] == "generate_listing"

    updated = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    assert updated["version"] == 2
    assert updated["status"] == "needs_confirmation"
    assert updated["transcript"] == {
        "voice_note_id": voice["id"],
        "language": "hi",
        "text": "यह हाथ से बना हुआ कपड़े का उत्पाद है।",
    }
    assert updated["listing"]["description_hi"] == updated["transcript"]["text"]
    assert updated["listing"]["description_en"] is None
    assert updated["field_confidence"] == {}
    assert set(updated["missing_fields"]) == set(updated["fields"])
    assert len(voice_service_override.calls) == 1

    replay = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/generate-listing",
        headers={**headers, "Idempotency-Key": key},
        json=request,
    )
    changed = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/generate-listing",
        headers={**headers, "Idempotency-Key": key},
        json={**request, "target_languages": ["hi"]},
    )
    assert replay.status_code == 202
    assert replay.json() == started.json()
    assert changed.status_code == 409


def test_generation_failure_is_persisted_for_polling(
    voice_service_override: FakeTranscriber,
) -> None:
    voice_service_override.error = ApiError(
        503,
        "SPEECH_PROVIDER_UNAVAILABLE",
        "Local speech transcription is temporarily unavailable.",
    )
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    image = upload_image(headers, draft_id)
    voice = upload_voice(headers, draft_id).json()
    accept_consent(headers)

    started = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/generate-listing",
        headers={**headers, "Idempotency-Key": str(uuid4())},
        json={
            "voice_note_id": voice["id"],
            "image_id": image["id"],
            "target_languages": ["hi", "en"],
        },
    )

    operation = client.get(started.headers["location"], headers=headers).json()
    updated = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers).json()
    assert operation["status"] == "failed"
    assert operation["error"]["code"] == "SPEECH_PROVIDER_UNAVAILABLE"
    assert updated["status"] == "failed"
    assert updated["last_processing_error"]["code"] == "SPEECH_PROVIDER_UNAVAILABLE"


def test_generation_rejects_missing_media_duplicate_work_and_approved_draft() -> None:
    headers = login_headers()
    draft = create_draft(headers)
    draft_id = str(draft["id"])
    image = upload_image(headers, draft_id)
    voice = upload_voice(headers, draft_id).json()
    accept_consent(headers)
    token = headers["Authorization"].removeprefix("Bearer ")
    user = get_auth_service().authenticate(token)
    service = app.dependency_overrides[get_voice_service]()
    request = GenerateListingRequest(
        voice_note_id=voice["id"],
        image_id=image["id"],
        target_languages=["hi", "en"],
    )
    operation, _ = service.start_listing_generation(user, draft_id, request, str(uuid4()))
    with pytest.raises(ApiError) as duplicate:
        service.start_listing_generation(user, draft_id, request, str(uuid4()))
    assert duplicate.value.status_code == 409
    with get_database().session() as session, session.begin():
        stored_operation = session.get(Operation, operation.id)
        assert stored_operation is not None
        stored_operation.status = "failed"
        stored_operation.error = {
            "code": "TEST_CLEANUP",
            "message": "Test cleanup.",
            "details": {},
        }
        row = session.get(CatalogDraft, draft_id)
        assert row is not None
        payload = dict(row.payload)
        payload["status"] = "approved"
        row.status = "approved"
        row.payload = payload

    approved_upload = upload_voice(headers, draft_id)
    with pytest.raises(ApiError) as approved_generation:
        service.start_listing_generation(user, draft_id, request, str(uuid4()))
    assert approved_upload.status_code == 400
    assert approved_generation.value.status_code == 400


def test_voice_openapi_surface_matches_frozen_contract() -> None:
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    upload = paths["/api/v1/catalog/drafts/{draft_id}/voice-notes"]["post"]
    generation = paths["/api/v1/catalog/drafts/{draft_id}/generate-listing"]["post"]

    assert upload["requestBody"]["content"]["multipart/form-data"]
    assert upload["responses"]["201"]
    assert generation["responses"]["202"]
    assert any(parameter["name"] == "Idempotency-Key" for parameter in generation["parameters"])
    assert get_settings().speech_provider == "faster_whisper"
