from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from sqlalchemy import func, select

from app.core.config import Settings
from app.core.errors import ApiError
from app.db.models import (
    CatalogDraft,
    DraftCreateIdempotency,
    OtpIdempotency,
    OtpRequest,
)
from app.db.session import Database, normalize_database_url
from app.schemas.catalog import DraftCreate, DraftPatch, ProductFieldsUpdate
from app.schemas.profile import ProfileUpdate
from app.services.auth import AuthService
from app.services.catalog import CatalogService


def database_settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        jwt_secret="persistence-test-secret-at-least-32-characters",
        database_url=f"sqlite+pysqlite:///{path}",
        database_auto_create=True,
    )


def authenticated_user(auth: AuthService, phone: str = "+919999999999"):
    otp = auth.request_otp(phone, str(uuid4()))
    login = auth.verify_otp(otp.request_id, "123456")
    return login, auth.authenticate(login.access_token)


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
