from __future__ import annotations

import mimetypes
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.errors import ApiError
from app.storage.base import normalized_media_key


class SupabaseMediaStorage:
    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None) -> None:
        if settings.supabase_url is None or settings.supabase_secret_key is None:
            raise ApiError(503, "STORAGE_UNAVAILABLE", "Media storage is unavailable.")
        self.base_url = f"{settings.supabase_url.rstrip('/')}/storage/v1"
        self.secret = settings.supabase_secret_key.get_secret_value()
        self.private_bucket = settings.supabase_private_bucket
        self.public_bucket = settings.supabase_public_bucket
        self.signed_url_ttl_seconds = settings.supabase_signed_url_ttl_seconds
        self.client = httpx.Client(
            headers={
                "apikey": self.secret,
                "Authorization": f"Bearer {self.secret}",
            },
            timeout=settings.supabase_storage_timeout_seconds,
            transport=transport,
        )

    def is_available(self) -> bool:
        expected = {
            self.private_bucket: False,
            self.public_bucket: True,
        }
        for bucket, expected_public in expected.items():
            try:
                response = self._request("GET", f"/bucket/{quote(bucket, safe='')}")
                payload = response.json()
            except (ApiError, ValueError):
                return False
            if (
                response.status_code != 200
                or not isinstance(payload, dict)
                or payload.get("id") != bucket
                or payload.get("public") is not expected_public
            ):
                return False
        return True

    def save(self, key: str, content: bytes) -> None:
        normalized = normalized_media_key(key)
        content_type = mimetypes.guess_type(normalized)[0] or "application/octet-stream"
        response = self._request(
            "POST",
            self._object_path(normalized),
            content=content,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )
        if response.status_code not in {200, 201}:
            raise self._unavailable()

    def read(self, key: str) -> bytes:
        normalized = normalized_media_key(key)
        bucket = self._bucket(normalized)
        route = "public" if bucket == self.public_bucket else "authenticated"
        response = self._request(
            "GET",
            f"/object/{route}/{quote(bucket, safe='')}/{quote(normalized, safe='/')}",
        )
        if response.status_code != 200:
            raise self._unavailable()
        return response.content

    def delete(self, key: str) -> None:
        normalized = normalized_media_key(key)
        try:
            self._request("DELETE", self._object_path(normalized))
        except ApiError:
            return

    def url(self, key: str) -> str:
        normalized = normalized_media_key(key)
        bucket = self._bucket(normalized)
        encoded = quote(normalized, safe="/")
        if bucket == self.public_bucket:
            return f"{self.base_url}/object/public/{quote(bucket, safe='')}/{encoded}"

        response = self._request(
            "POST",
            f"/object/sign/{quote(bucket, safe='')}/{encoded}",
            json={"expiresIn": self.signed_url_ttl_seconds},
        )
        if response.status_code != 200:
            raise self._unavailable()
        try:
            signed_path = response.json()["signedURL"]
        except (KeyError, TypeError, ValueError) as error:
            raise self._unavailable() from error
        if not isinstance(signed_path, str) or not signed_path.startswith("/"):
            raise self._unavailable()
        return f"{self.base_url}{signed_path}"

    def _bucket(self, key: str) -> str:
        return self.public_bucket if key.startswith("public/") else self.private_bucket

    def _object_path(self, key: str) -> str:
        return f"/object/{quote(self._bucket(key), safe='')}/{quote(key, safe='/')}"

    def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            return self.client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as error:
            raise self._unavailable() from error

    @staticmethod
    def _unavailable() -> ApiError:
        return ApiError(503, "STORAGE_UNAVAILABLE", "Media storage is unavailable.")
