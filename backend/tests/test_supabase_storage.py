from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ApiError
from app.db.session import Database
from app.schemas.catalog import DraftCreate
from app.services.auth import AuthService
from app.services.catalog import CatalogService
from app.services.media import MediaService
from app.storage.factory import create_media_storage
from app.storage.supabase import SupabaseMediaStorage


def supabase_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "test",
        "media_storage": "supabase",
        "supabase_url": "https://project.supabase.co",
        "supabase_secret_key": "sb_secret_test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_supabase_storage_routes_private_and_public_objects() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/bucket/kalasetu-private"):
            return httpx.Response(200, json={"id": "kalasetu-private", "public": False})
        if request.url.path.endswith("/bucket/kalasetu-public"):
            return httpx.Response(200, json={"id": "kalasetu-public", "public": True})
        if request.url.path.startswith("/storage/v1/object/sign/"):
            assert json.loads(request.content) == {"expiresIn": 3600}
            return httpx.Response(
                200,
                json={"signedURL": "/object/sign/kalasetu-private/drafts/u1/photo.jpg?t=x"},
            )
        if request.method == "GET":
            return httpx.Response(200, content=b"stored")
        return httpx.Response(200, json={"Key": "ok"})

    storage = SupabaseMediaStorage(
        supabase_settings(),
        transport=httpx.MockTransport(handler),
    )
    assert storage.is_available()
    storage.save("drafts/u1/photo.jpg", b"image")
    assert storage.read("drafts/u1/photo.jpg") == b"stored"
    assert storage.url("drafts/u1/photo.jpg") == (
        "https://project.supabase.co/storage/v1/object/sign/"
        "kalasetu-private/drafts/u1/photo.jpg?t=x"
    )
    storage.save("public/share_1/product.jpg", b"public-image")
    assert storage.url("public/share_1/product.jpg") == (
        "https://project.supabase.co/storage/v1/object/public/"
        "kalasetu-public/public/share_1/product.jpg"
    )
    storage.delete("drafts/u1/photo.jpg")

    assert requests[2].method == "POST"
    assert requests[2].url.path.endswith(
        "/object/kalasetu-private/drafts/u1/photo.jpg"
    )
    assert requests[2].headers["authorization"] == "Bearer sb_secret_test"
    assert requests[2].headers["apikey"] == "sb_secret_test"
    assert requests[2].headers["x-upsert"] == "true"
    assert requests[3].url.path.endswith(
        "/object/authenticated/kalasetu-private/drafts/u1/photo.jpg"
    )
    assert requests[5].url.path.endswith(
        "/object/kalasetu-public/public/share_1/product.jpg"
    )


def test_supabase_storage_normalizes_errors_without_leaking_provider_details() -> None:
    storage = SupabaseMediaStorage(
        supabase_settings(),
        transport=httpx.MockTransport(
            lambda request: httpx.Response(500, json={"message": "sensitive provider detail"})
        ),
    )

    with pytest.raises(ApiError) as error:
        storage.read("drafts/u1/missing.jpg")

    assert error.value.code == "STORAGE_UNAVAILABLE"
    assert "sensitive" not in error.value.message
    assert not storage.is_available()


def test_supabase_storage_configuration_fails_closed() -> None:
    with pytest.raises(ValidationError, match="SUPABASE_URL and SUPABASE_SECRET_KEY"):
        Settings(_env_file=None, environment="test", media_storage="supabase")
    with pytest.raises(ValidationError, match="SUPABASE_URL must use HTTPS"):
        supabase_settings(
            environment="production",
            jwt_secret="x" * 32,
            dev_otp=None,
            database_auto_create=False,
            public_api_base_url="https://api.example.test",
            public_share_web_base_url="https://share.example.test",
            cors_origins=["https://app.example.test"],
            media_url_base="https://media.example.test",
            supabase_url="http://project.supabase.co",
        )

    assert isinstance(create_media_storage(supabase_settings()), SupabaseMediaStorage)


def test_persisted_drafts_refresh_expiring_private_image_urls(tmp_path: Path) -> None:
    class RotatingSignedStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.url_generation = 0

        def is_available(self) -> bool:
            return True

        def save(self, key: str, content: bytes) -> None:
            self.objects[key] = content

        def read(self, key: str) -> bytes:
            return self.objects[key]

        def delete(self, key: str) -> None:
            self.objects.pop(key, None)

        def url(self, key: str) -> str:
            self.url_generation += 1
            return f"https://signed.example/{self.url_generation}/{key}"

    image_buffer = BytesIO()
    Image.new("RGB", (16, 16), "blue").save(image_buffer, format="JPEG")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite+pysqlite:///{tmp_path / 'signed-urls.db'}",
        database_auto_create=True,
    )
    database = Database(settings)
    storage = RotatingSignedStorage()
    auth = AuthService(settings, database)
    catalog = CatalogService(settings, database, storage)
    media = MediaService(settings, database, storage)
    otp = auth.request_otp("+919999999999", str(uuid4()))
    login = auth.verify_otp(otp.request_id, "123456")
    user = auth.authenticate(login.access_token)
    draft = catalog.create_draft(
        user,
        DraftCreate(craft_category="textile", source_language="hi"),
        str(uuid4()),
    )
    uploaded = media.upload_image(
        user,
        draft.id,
        image_buffer.getvalue(),
        True,
        str(uuid4()),
    )

    first_fetch = catalog.get_draft(user, draft.id)
    second_fetch = catalog.get_draft(user, draft.id)
    listing = catalog.list_drafts(user, limit=10, cursor=None, status=None)

    assert uploaded.original_url != first_fetch.images[0].original_url
    assert first_fetch.images[0].original_url != second_fetch.images[0].original_url
    assert listing.items[0].thumbnail_url not in {
        uploaded.original_url,
        first_fetch.images[0].original_url,
        second_fetch.images[0].original_url,
    }
    database.dispose()
