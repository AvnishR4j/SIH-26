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
from app.db.session import get_database
from app.main import app
from app.schemas.catalog import Listing, ProductFields
from app.services.auth import get_auth_service
from app.services.catalogue_generation import CatalogueGenerationResult
from app.services.speech import TranscriptionResult
from app.services.voice import VoiceService, get_voice_service
from app.storage.local import get_media_storage

client = TestClient(app)


class JourneyTranscriber:
    def transcribe(self, content: bytes, language: str) -> TranscriptionResult:
        assert content
        assert language == "hi"
        return TranscriptionResult(
            text=(
                "यह सूती दुपट्टा हाथ की चिकनकारी से बना है। आकार 2.4 मीटर गुणा 1 मीटर है और दो उपलब्ध हैं।"
            ),
            language="hi",
        )


class JourneyCatalogueGenerator:
    def generate(
        self,
        draft: object,
        transcript: str,
        source_language: str,
        target_languages: list[str],
    ) -> CatalogueGenerationResult:
        del draft
        assert transcript
        assert source_language == "hi"
        assert target_languages == ["hi", "en"]
        return CatalogueGenerationResult(
            fields=ProductFields(
                product_type="dupatta",
                material="cotton",
                technique="chikankari hand embroidery",
                color="white",
                dimensions="2.4 m x 1 m",
                quantity_available=2,
                production_time_days=7,
                care="gentle hand wash",
                origin="Lucknow",
            ),
            listing=Listing(
                title_hi="हाथ की चिकनकारी वाला सूती दुपट्टा",
                title_en="Hand-Embroidered Chikankari Cotton Dupatta",
                description_hi="लखनऊ में हाथ से बना सूती चिकनकारी दुपट्टा।",
                description_en="A cotton Chikankari dupatta handmade in Lucknow.",
                tags=["chikankari", "cotton", "handmade"],
            ),
            field_confidence={
                "product_type": 0.98,
                "material": 0.97,
                "technique": 0.96,
                "dimensions": 0.95,
                "quantity_available": 0.95,
            },
        )


@pytest.fixture(autouse=True)
def journey_services() -> Iterator[None]:
    get_auth_service().reset()
    service = VoiceService(
        get_settings(),
        get_database(),
        get_media_storage(),
        JourneyTranscriber(),
        JourneyCatalogueGenerator(),
    )
    app.dependency_overrides[get_voice_service] = lambda: service
    yield
    app.dependency_overrides.pop(get_voice_service, None)
    get_auth_service().reset()


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (120, 80), (170, 65, 35)).save(output, format="JPEG")
    return output.getvalue()


def wav_bytes(duration_seconds: float = 1.0, sample_rate: int = 8_000) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        frames = b"".join(
            pack("<h", round(2_000 * sin(tau * 220 * index / sample_rate)))
            for index in range(round(duration_seconds * sample_rate))
        )
        audio.writeframes(frames)
    return output.getvalue()


def idempotency_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    return {**(headers or {}), "Idempotency-Key": str(uuid4())}


def test_complete_flutter_facing_mvp_journey() -> None:
    otp = client.post(
        "/api/v1/auth/request-otp",
        headers=idempotency_headers(),
        json={"phone": "+919999999999"},
    )
    assert otp.status_code == 202
    login = client.post(
        "/api/v1/auth/verify-otp",
        json={"request_id": otp.json()["request_id"], "otp": "123456"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    profile = client.patch(
        "/api/v1/me",
        headers=headers,
        json={"name": "Sita Devi", "cluster": "Lucknow Chikankari SHG"},
    )
    consent = client.put(
        "/api/v1/me/consents/media-processing",
        headers=headers,
        json={"accepted": True, "policy_version": "2026-08-29"},
    )
    assert profile.status_code == consent.status_code == 200

    created = client.post(
        "/api/v1/catalog/drafts",
        headers=idempotency_headers(headers),
        json={"craft_category": "textile", "source_language": "hi"},
    )
    assert created.status_code == 201
    draft_id = created.json()["id"]

    uploaded_image = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images",
        headers=idempotency_headers(headers),
        data={"is_primary": "true"},
        files={"image": ("product.jpg", image_bytes(), "image/jpeg")},
    )
    assert uploaded_image.status_code == 201
    image_id = uploaded_image.json()["id"]

    enhancement = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}/enhance",
        headers=idempotency_headers(headers),
        json={
            "background": "neutral",
            "crop_style": "marketplace_square",
            "preserve_original": True,
        },
    )
    assert enhancement.status_code == 202
    assert enhancement.headers["location"] == (f"/api/v1/operations/{enhancement.json()['id']}")
    enhancement_operation = client.get(enhancement.headers["location"], headers=headers)
    assert enhancement_operation.status_code == 200
    assert enhancement_operation.json()["status"] == "succeeded"

    selected = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}/images/{image_id}",
        headers=headers,
        json={"version": 1, "selected_variant": "enhanced"},
    )
    assert selected.status_code == 200
    assert selected.json()["version"] == 2

    uploaded_voice = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/voice-notes",
        headers=idempotency_headers(headers),
        data={"language": "hi"},
        files={"audio": ("description.wav", wav_bytes(), "audio/wav")},
    )
    assert uploaded_voice.status_code == 201

    generation = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/generate-listing",
        headers=idempotency_headers(headers),
        json={
            "voice_note_id": uploaded_voice.json()["id"],
            "image_id": image_id,
            "target_languages": ["hi", "en"],
        },
    )
    assert generation.status_code == 202
    generated_operation = client.get(generation.headers["location"], headers=headers)
    assert generated_operation.status_code == 200
    assert generated_operation.json()["status"] == "succeeded"

    generated = client.get(f"/api/v1/catalog/drafts/{draft_id}", headers=headers)
    assert generated.status_code == 200
    assert generated.json()["version"] == 3
    assert generated.json()["status"] == "needs_confirmation"
    assert generated.json()["missing_fields"] == []
    assert generated.json()["images"][0]["selected_variant"] == "enhanced"

    pricing = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/pricing/suggest",
        headers=idempotency_headers(headers),
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
    assert pricing.status_code == 200
    assert pricing.json()["draft_version"] == 4

    approval = client.post(
        f"/api/v1/catalog/drafts/{draft_id}/approve",
        headers=idempotency_headers(headers),
        json={
            "version": 4,
            "approved_price_paise": pricing.json()["recommended_paise"],
            "approval_note": "Artisan confirmed the listing, image, and price.",
        },
    )
    assert approval.status_code == 201
    assert approval.json()["status"] == "approved"

    share = client.get(f"/api/v1/share/{approval.json()['public_share_id']}")
    assert share.status_code == 200
    assert share.json()["title"] == "Hand-Embroidered Chikankari Cotton Dupatta"
    assert share.json()["image_url"].startswith("http://testserver/media/public/")
    assert "+919999999999" not in str(share.json())

    enquiry = client.post(
        f"/api/v1/share/{approval.json()['public_share_id']}/enquiries",
        headers=idempotency_headers(),
        json={
            "buyer_name": "Aarav Retail",
            "buyer_phone": "+918888888888",
            "message": "Interested in 20 pieces",
            "quantity_requested": 20,
            "consent_to_contact": True,
        },
    )
    assert enquiry.status_code == 201

    immutable = client.patch(
        f"/api/v1/catalog/drafts/{draft_id}",
        headers=headers,
        json={"version": 5, "fields": {"color": "blue"}},
    )
    assert immutable.status_code == 400
    assert immutable.json()["error"]["code"] == "INVALID_STATE"
