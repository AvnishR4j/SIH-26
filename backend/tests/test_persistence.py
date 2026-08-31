import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from PIL import Image
from sqlalchemy import func, select

from app.core.config import Settings
from app.core.errors import ApiError
from app.db.models import (
    BuyerEnquiry,
    CatalogDraft,
    DraftCreateIdempotency,
    OtpIdempotency,
    OtpRequest,
)
from app.db.session import Database, normalize_database_url
from app.schemas.catalog import (
    DraftCreate,
    DraftImagePatch,
    DraftPatch,
    GenerateListingRequest,
    ImageEnhancementRequest,
    ListingUpdate,
    PricingSuggestionRequest,
    ProductFieldsUpdate,
)
from app.schemas.profile import ProfileUpdate
from app.schemas.sharing import ApprovalRequest, EnquiryRequest
from app.services.auth import AuthService
from app.services.catalog import CatalogService
from app.services.media import MediaService
from app.services.pricing import PricingService
from app.services.sharing import SharingService
from app.services.speech import TranscriptionResult
from app.services.voice import VoiceService
from app.storage.local import LocalMediaStorage


def database_settings(path: Path, media_path: Path | None = None) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        jwt_secret="persistence-test-secret-at-least-32-characters",
        database_url=f"sqlite+pysqlite:///{path}",
        database_auto_create=True,
        media_local_dir=media_path or path.parent / "media",
        media_url_base="http://testserver/media",
    )


def authenticated_user(auth: AuthService, phone: str = "+919999999999"):
    otp = auth.request_otp(phone, str(uuid4()))
    login = auth.verify_otp(otp.request_id, "123456")
    return login, auth.authenticate(login.access_token)


def jpeg_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 60), (120, 40, 20)).save(output, format="JPEG")
    return output.getvalue()


def wav_bytes() -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(8_000)
        audio.writeframes(b"\0\0" * 8_000)
    return output.getvalue()


class RestartTranscriber:
    def transcribe(self, content: bytes, language: str) -> TranscriptionResult:
        assert content.startswith(b"RIFF")
        assert language == "hi"
        return TranscriptionResult(text="हाथ से बना कपड़े का उत्पाद", language="hi")


def test_postgres_urls_use_the_installed_psycopg_driver() -> None:
    assert normalize_database_url("postgresql://user:pass@db/kalasetu") == (
        "postgresql+psycopg://user:pass@db/kalasetu"
    )
    assert normalize_database_url("postgres://user:pass@db/kalasetu") == (
        "postgresql+psycopg://user:pass@db/kalasetu"
    )


def test_profile_token_and_draft_survive_database_reinitialization(tmp_path: Path) -> None:
    settings = database_settings(tmp_path / "restart.db")
    first_database = Database(settings)
    first_auth = AuthService(settings, first_database)
    first_catalog = CatalogService(settings, first_database)
    login, user = authenticated_user(first_auth)

    first_auth.update_profile(
        user,
        ProfileUpdate(
            name="Sita Devi",
            cluster="Lucknow Chikankari SHG",
            craft_categories=["textile", "embroidery"],
        ),
    )
    draft = first_catalog.create_draft(
        user,
        DraftCreate(craft_category="textile", source_language="hi"),
        str(uuid4()),
    )
    first_catalog.update_draft(
        user,
        draft.id,
        DraftPatch(version=1, fields=ProductFieldsUpdate(material="cotton")),
    )
    first_database.dispose()

    second_database = Database(settings)
    second_auth = AuthService(settings, second_database)
    second_catalog = CatalogService(settings, second_database)
    restored_user = second_auth.authenticate(login.access_token)
    restored_profile = second_auth.profile(restored_user)
    restored_draft = second_catalog.get_draft(restored_user, draft.id)

    assert restored_profile.name == "Sita Devi"
    assert restored_profile.cluster == "Lucknow Chikankari SHG"
    assert restored_profile.craft_categories == ["textile", "embroidery"]
    assert restored_draft.version == 2
    assert restored_draft.fields.material == "cotton"
    second_database.dispose()


def test_pricing_and_replay_survive_database_reinitialization(tmp_path: Path) -> None:
    settings = database_settings(tmp_path / "pricing-restart.db")
    first_database = Database(settings)
    first_auth = AuthService(settings, first_database)
    first_catalog = CatalogService(settings, first_database)
    first_pricing = PricingService(settings, first_database)
    login, user = authenticated_user(first_auth)
    draft = first_catalog.create_draft(
        user,
        DraftCreate(craft_category="textile", source_language="hi"),
        str(uuid4()),
    )
    key = str(uuid4())
    request = PricingSuggestionRequest(
        version=1,
        material_cost_paise=30_000,
        labour_hours=8,
        hourly_rate_paise=5_000,
        packaging_cost_paise=5_000,
        logistics_buffer_paise=0,
        benchmark_category="cotton_dupatta",
    )
    original = first_pricing.suggest_price(user, draft.id, request, key)
    first_database.dispose()

    second_database = Database(settings)
    second_auth = AuthService(settings, second_database)
    second_catalog = CatalogService(settings, second_database)
    second_pricing = PricingService(settings, second_database)
    restored_user = second_auth.authenticate(login.access_token)
    restored = second_catalog.get_draft(restored_user, draft.id)
    replay = second_pricing.suggest_price(restored_user, draft.id, request, key)

    assert restored.version == 2
    assert restored.pricing == original
    assert replay == original
    second_database.dispose()


def test_otp_is_hashed_and_can_only_be_consumed_once(tmp_path: Path) -> None:
    settings = database_settings(tmp_path / "otp.db")
    database = Database(settings)
    first = AuthService(settings, database)
    second = AuthService(settings, database)
    otp = first.request_otp("+919999999999", str(uuid4()))

    with database.session() as session:
        stored = session.get(OtpRequest, otp.request_id)
        assert stored is not None
        assert stored.otp_hash != "123456"
        assert len(stored.otp_hash) == 64

    barrier = Barrier(2)

    def consume(service: AuthService) -> str:
        barrier.wait()
        try:
            service.verify_otp(otp.request_id, "123456")
            return "accepted"
        except ApiError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(consume, (first, second)))

    assert sorted(outcomes) == ["UNAUTHORIZED", "accepted"]
    database.dispose()


def test_idempotent_creates_are_shared_by_service_instances(tmp_path: Path) -> None:
    settings = database_settings(tmp_path / "idempotency.db")
    database = Database(settings)
    first_auth = AuthService(settings, database)
    second_auth = AuthService(settings, database)
    key = str(uuid4())
    barrier = Barrier(2)

    def request(service: AuthService) -> str:
        barrier.wait()
        return service.request_otp("+919999999999", key).request_id

    with ThreadPoolExecutor(max_workers=2) as executor:
        request_ids = list(executor.map(request, (first_auth, second_auth)))

    assert len(set(request_ids)) == 1
    _, user = authenticated_user(first_auth)
    first_catalog = CatalogService(settings, database)
    second_catalog = CatalogService(settings, database)
    draft_key = str(uuid4())
    create = DraftCreate(craft_category="pottery", source_language="hi")
    draft_barrier = Barrier(2)

    def create_draft(service: CatalogService) -> str:
        draft_barrier.wait()
        return service.create_draft(user, create, draft_key).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        draft_ids = list(executor.map(create_draft, (first_catalog, second_catalog)))

    assert len(set(draft_ids)) == 1
    with database.session() as session:
        assert session.scalar(select(func.count(CatalogDraft.id))) == 1
    database.dispose()


def test_idempotency_keys_can_be_reused_after_their_replay_window(tmp_path: Path) -> None:
    settings = database_settings(tmp_path / "expiry.db")
    database = Database(settings)
    auth = AuthService(settings, database)
    otp_key = str(uuid4())
    first_otp = auth.request_otp("+919999999999", otp_key)
    with database.session() as session, session.begin():
        replay = session.scalar(
            select(OtpIdempotency).where(OtpIdempotency.idempotency_key == otp_key)
        )
        assert replay is not None
        replay.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    second_otp = auth.request_otp("+919999999999", otp_key)
    assert second_otp.request_id != first_otp.request_id
    login = auth.verify_otp(second_otp.request_id, "123456")
    user = auth.authenticate(login.access_token)

    catalog = CatalogService(settings, database)
    draft_key = str(uuid4())
    first_draft = catalog.create_draft(
        user,
        DraftCreate(craft_category="textile", source_language="hi"),
        draft_key,
    )
    with database.session() as session, session.begin():
        replay = session.scalar(
            select(DraftCreateIdempotency).where(
                DraftCreateIdempotency.idempotency_key == draft_key
            )
        )
        assert replay is not None
        replay.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    second_draft = catalog.create_draft(
        user,
        DraftCreate(craft_category="pottery", source_language="hi"),
        draft_key,
    )
    assert second_draft.id != first_draft.id
    database.dispose()


def test_media_and_operations_survive_database_reinitialization(tmp_path: Path) -> None:
    media_path = tmp_path / "media"
    settings = database_settings(tmp_path / "media-restart.db", media_path)
    first_database = Database(settings)
    first_auth = AuthService(settings, first_database)
    first_catalog = CatalogService(settings, first_database)
    first_media = MediaService(
        settings,
        first_database,
        LocalMediaStorage(settings),
    )
    first_voice = VoiceService(
        settings,
        first_database,
        LocalMediaStorage(settings),
        RestartTranscriber(),
    )
    login, user = authenticated_user(first_auth)
    first_auth.update_consent(user, True, settings.media_consent_policy_version)
    user = first_auth.authenticate(login.access_token)
    draft = first_catalog.create_draft(
        user,
        DraftCreate(craft_category="textile", source_language="hi"),
        str(uuid4()),
    )
    image = first_media.upload_image(
        user,
        draft.id,
        jpeg_bytes(),
        True,
        str(uuid4()),
    )
    image_operation, _ = first_media.start_image_enhancement(
        user,
        draft.id,
        image.id,
        ImageEnhancementRequest(),
        str(uuid4()),
    )
    first_media.complete_image_enhancement(user.id, image_operation.id)
    voice = first_voice.upload_voice_note(
        user,
        draft.id,
        wav_bytes(),
        "hi",
        str(uuid4()),
    )
    listing_operation, _ = first_voice.start_listing_generation(
        user,
        draft.id,
        GenerateListingRequest(
            voice_note_id=voice.id,
            image_id=image.id,
            target_languages=["hi", "en"],
        ),
        str(uuid4()),
    )
    first_voice.complete_listing_generation(user.id, listing_operation.id)
    first_database.dispose()

    second_database = Database(settings)
    second_auth = AuthService(settings, second_database)
    second_catalog = CatalogService(settings, second_database)
    second_media = MediaService(
        settings,
        second_database,
        LocalMediaStorage(settings),
    )
    restored_user = second_auth.authenticate(login.access_token)
    restored_draft = second_catalog.get_draft(restored_user, draft.id)
    restored_image_operation = second_media.get_operation(restored_user, image_operation.id)
    restored_listing_operation = second_media.get_operation(restored_user, listing_operation.id)

    assert restored_image_operation.status == "succeeded"
    assert restored_listing_operation.status == "succeeded"
    assert restored_draft.images[0].enhancement_status == "succeeded"
    assert restored_draft.images[0].enhanced_url is not None
    assert restored_draft.voice_notes[0].id == voice.id
    assert restored_draft.transcript is not None
    assert restored_draft.transcript.text == "हाथ से बना कपड़े का उत्पाद"
    assert len(list(media_path.rglob("original.jpg"))) == 1
    assert len(list(media_path.rglob("original.wav"))) == 1
    assert len(list(media_path.rglob("enhanced.jpg"))) == 1
    second_database.dispose()


def test_approved_share_and_enquiry_survive_database_reinitialization(
    tmp_path: Path,
) -> None:
    media_path = tmp_path / "share-media"
    settings = database_settings(tmp_path / "share-restart.db", media_path)
    storage = LocalMediaStorage(settings)
    first_database = Database(settings)
    auth = AuthService(settings, first_database)
    catalog = CatalogService(settings, first_database)
    media = MediaService(settings, first_database, storage)
    pricing = PricingService(settings, first_database)
    sharing = SharingService(settings, first_database, storage)
    login, user = authenticated_user(auth)
    draft = catalog.create_draft(
        user,
        DraftCreate(craft_category="textile", source_language="hi"),
        str(uuid4()),
    )
    image = media.upload_image(user, draft.id, jpeg_bytes(), True, str(uuid4()))
    detailed = catalog.update_draft(
        user,
        draft.id,
        DraftPatch(
            version=1,
            fields=ProductFieldsUpdate(
                product_type="dupatta",
                material="cotton",
                technique="hand embroidery",
                dimensions="2.4 m x 1 m",
                quantity_available=2,
                production_time_days=7,
            ),
            listing=ListingUpdate(
                title_hi="हाथ की कढ़ाई वाला दुपट्टा",
                title_en="Hand Embroidered Dupatta",
                description_hi="सूती कपड़े पर हाथ की कढ़ाई।",
                description_en="Hand embroidery on cotton fabric.",
            ),
        ),
    )
    selected = media.update_image(
        user,
        draft.id,
        image.id,
        DraftImagePatch(version=detailed.version, selected_variant="original"),
    )
    suggestion = pricing.suggest_price(
        user,
        draft.id,
        PricingSuggestionRequest(
            version=selected.version,
            material_cost_paise=30_000,
            labour_hours=8,
            hourly_rate_paise=5_000,
            packaging_cost_paise=5_000,
            logistics_buffer_paise=0,
            benchmark_category="cotton_dupatta",
        ),
        str(uuid4()),
    )
    approved = sharing.approve_draft(
        user,
        draft.id,
        ApprovalRequest(version=suggestion.draft_version, approved_price_paise=95_000),
        str(uuid4()),
    )
    enquiry_key = str(uuid4())
    enquiry_request = EnquiryRequest(
        buyer_name="Aarav Retail",
        buyer_phone="+918888888888",
        message="Interested in 20 pieces",
        quantity_requested=20,
        consent_to_contact=True,
    )
    original_enquiry = sharing.submit_enquiry(
        approved.public_share_id,
        enquiry_request,
        enquiry_key,
    )
    original_card = sharing.get_share_card(approved.public_share_id)
    first_database.dispose()

    second_database = Database(settings)
    restored_auth = AuthService(settings, second_database)
    restored_catalog = CatalogService(settings, second_database)
    restored_sharing = SharingService(settings, second_database, LocalMediaStorage(settings))
    restored_user = restored_auth.authenticate(login.access_token)
    restored_draft = restored_catalog.get_draft(restored_user, draft.id)
    restored_card = restored_sharing.get_share_card(approved.public_share_id)
    replay = restored_sharing.submit_enquiry(
        approved.public_share_id,
        enquiry_request,
        enquiry_key,
    )

    assert restored_draft.status == "approved"
    assert restored_card == original_card
    assert replay == original_enquiry
    assert len(list(media_path.glob("public/*/product.jpg"))) == 1
    with second_database.session() as session:
        assert session.scalar(select(func.count(BuyerEnquiry.id))) == 1
    second_database.dispose()
