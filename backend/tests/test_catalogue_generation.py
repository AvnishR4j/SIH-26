import json
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import types
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.catalog import Draft, ProductFields
from app.services.catalogue_generation import (
    GeminiCatalogueGenerator,
    GeminiCatalogueResponse,
    GeneratedListing,
    GroundedInteger,
    GroundedText,
    MockCatalogueGenerator,
)


class FakeModels:
    def __init__(self, parsed: object = None, error: Exception | None = None) -> None:
        self.parsed = parsed
        self.error = error
        self.calls: list[dict[str, object]] = []

    def generate_content(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return SimpleNamespace(parsed=self.parsed, text=None)


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.models = models


def draft(**field_overrides: object) -> Draft:
    now = datetime.now(UTC)
    fields = ProductFields(
        product_type=None,
        material=None,
        technique=None,
        color=None,
        dimensions=None,
        quantity_available=None,
        production_time_days=None,
        care=None,
        origin=None,
    ).model_copy(update=field_overrides)
    return Draft(
        id="draft_test",
        version=1,
        status="media_ready",
        craft_category="textile",
        source_language="hi",
        initial_notes=None,
        fields=fields,
        listing=None,
        images=[],
        voice_notes=[],
        transcript=None,
        field_confidence={},
        missing_fields=[],
        pricing=None,
        last_processing_error=None,
        created_at=now,
        updated_at=now,
    )


def gemini_settings(**overrides: object) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        catalogue_generation_provider="gemini",
        gemini_api_key="test-only-key",
        **overrides,
    )


def generated_response() -> GeminiCatalogueResponse:
    return GeminiCatalogueResponse(
        product_type=GroundedText(value="dupatta", evidence="दुपट्टा", confidence=0.94),
        material=GroundedText(value="cotton", evidence="कॉटन", confidence=0.9),
        technique=GroundedText(
            value="chikankari",
            evidence="evidence not present",
            confidence=0.99,
        ),
        quantity_available=GroundedInteger(value=3, evidence="मात्रा 3", confidence=0.86),
        listing=GeneratedListing(
            title_hi="कॉटन दुपट्टा",
            title_en="Cotton Dupatta",
            description_hi="कारीगर द्वारा बनाया गया कॉटन दुपट्टा।",
            description_en="An artisan-made cotton dupatta.",
            source_evidence=["कॉटन का दुपट्टा", "मात्रा 3"],
        ),
    )


def test_mock_generator_remains_deterministic_default() -> None:
    result = MockCatalogueGenerator().generate(
        draft(),
        "यह हाथ से बना कपड़े का उत्पाद है।",
        "hi",
        ["hi", "en"],
    )

    assert result.fields == draft().fields
    assert result.listing.title_hi == "textile"
    assert result.listing.title_en == "textile"
    assert result.listing.description_hi == "यह हाथ से बना कपड़े का उत्पाद है।"
    assert result.listing.description_en is None


def test_gemini_output_requires_verbatim_evidence_and_preserves_artisan_fields() -> None:
    models = FakeModels(generated_response())
    generator = GeminiCatalogueGenerator(gemini_settings(), FakeClient(models))
    source = draft(material="artisan-confirmed cotton")
    transcript = "यह कॉटन का दुपट्टा है और मात्रा 3 है।"

    result = generator.generate(source, transcript, "hi", ["hi", "en"])

    assert result.fields.product_type == "dupatta"
    assert result.fields.material == "artisan-confirmed cotton"
    assert result.fields.technique is None
    assert result.fields.quantity_available == 3
    assert result.field_confidence == {"product_type": 0.94, "quantity_available": 0.86}
    assert result.listing.title_hi == "कॉटन दुपट्टा"
    assert result.listing.title_en == "Cotton Dupatta"
    assert result.listing.tags == ["textile", "dupatta", "artisan-confirmed cotton"]
    assert len(models.calls) == 1
    assert "test-only-key" not in str(models.calls[0])


def test_ungrounded_listing_is_discarded_without_discarding_grounded_fields() -> None:
    generated = generated_response().model_copy(
        update={
            "listing": generated_response().listing.model_copy(
                update={"source_evidence": ["not in transcript"]}
            )
        }
    )
    generator = GeminiCatalogueGenerator(
        gemini_settings(),
        FakeClient(FakeModels(generated)),
    )

    result = generator.generate(
        draft(),
        "यह कॉटन का दुपट्टा है और मात्रा 3 है।",
        "hi",
        ["hi", "en"],
    )

    assert result.fields.product_type == "dupatta"
    assert result.listing.title_hi is None
    assert result.listing.description_en is None


def test_generated_contact_details_are_not_copied_into_draft() -> None:
    generated = generated_response().model_copy(
        update={
            "origin": GroundedText(
                value="Call +919999999999",
                evidence="+919999999999",
                confidence=0.99,
            ),
            "listing": generated_response().listing.model_copy(
                update={"description_en": "Call +919999999999 to order."}
            ),
        }
    )
    generator = GeminiCatalogueGenerator(
        gemini_settings(),
        FakeClient(FakeModels(generated)),
    )

    result = generator.generate(
        draft(),
        "यह कॉटन का दुपट्टा है, मात्रा 3 है। +919999999999",
        "hi",
        ["hi", "en"],
    )

    assert result.fields.origin is None
    assert result.listing.title_hi is None
    assert result.listing.description_en is None


def test_gemini_provider_failure_uses_stable_error_without_provider_payload() -> None:
    generator = GeminiCatalogueGenerator(
        gemini_settings(),
        FakeClient(FakeModels(error=RuntimeError("private provider details"))),
    )

    with pytest.raises(ApiError) as error:
        generator.generate(draft(), "transcript", "en", ["en"])

    assert error.value.status_code == 503
    assert error.value.code == "AI_SERVICE_UNAVAILABLE"
    assert "private provider details" not in error.value.message


def test_gemini_provider_requires_server_side_key() -> None:
    for key in (None, ""):
        with pytest.raises(ValidationError, match="GEMINI_API_KEY"):
            Settings(
                _env_file=None,
                environment="test",
                catalogue_generation_provider="gemini",
                gemini_api_key=key,
            )


def test_official_sdk_serializes_schema_and_parses_typed_response() -> None:
    captured: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["api_key"] = request.headers.get("x-goog-api-key")
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "text": generated_response().model_dump_json(),
                                }
                            ],
                        },
                        "finishReason": "STOP",
                    }
                ]
            },
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handle))
    client = genai.Client(
        api_key="test-only-key",
        http_options=types.HttpOptions(httpx_client=http_client),
    )
    generator = GeminiCatalogueGenerator(gemini_settings(), client)

    result = generator.generate(
        draft(),
        "यह कॉटन का दुपट्टा है और मात्रा 3 है।",
        "hi",
        ["hi", "en"],
    )
    client.close()

    assert result.fields.product_type == "dupatta"
    assert captured["api_key"] == "test-only-key"
    assert ":generateContent" in str(captured["url"])
    generation_config = captured["body"]["generationConfig"]  # type: ignore[index]
    assert generation_config["responseMimeType"] == "application/json"
    assert generation_config["responseSchema"]["properties"]["material"]
