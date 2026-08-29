import os
from functools import lru_cache
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile

from app.core.config import REPOSITORY_ROOT, Settings, get_settings
from app.core.errors import ApiError


def local_media_root(settings: Settings) -> Path:
    configured = settings.media_local_dir.expanduser()
    return (
        configured.resolve()
        if configured.is_absolute()
        else (REPOSITORY_ROOT / configured).resolve()
    )


class LocalMediaStorage:
    def __init__(self, settings: Settings) -> None:
        self.root = local_media_root(settings)
        self.url_base = settings.media_url_base.rstrip("/")
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise ApiError(503, "STORAGE_UNAVAILABLE", "Media storage is unavailable.") from error

    def save(self, key: str, content: bytes) -> None:
        destination = self._path(key)
        temporary_path: Path | None = None
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with NamedTemporaryFile(dir=destination.parent, delete=False) as temporary:
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
                temporary_path = Path(temporary.name)
            temporary_path.replace(destination)
            destination.chmod(0o600)
        except OSError as error:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise ApiError(503, "STORAGE_UNAVAILABLE", "Media storage is unavailable.") from error

    def read(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except OSError as error:
            raise ApiError(503, "STORAGE_UNAVAILABLE", "Media storage is unavailable.") from error

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError:
            return

    def url(self, key: str) -> str:
        normalized = self._normalized_key(key)
        return f"{self.url_base}/{normalized}"

    def _path(self, key: str) -> Path:
        normalized = self._normalized_key(key)
        path = (self.root / normalized).resolve()
        if not path.is_relative_to(self.root):
            raise ApiError(500, "INTERNAL_ERROR", "The media key is invalid.")
        return path

    @staticmethod
    def _normalized_key(key: str) -> str:
        path = PurePosixPath(key)
        if (
            path.is_absolute()
            or not path.parts
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ApiError(500, "INTERNAL_ERROR", "The media key is invalid.")
        return path.as_posix()


@lru_cache
def get_media_storage() -> LocalMediaStorage:
    return LocalMediaStorage(get_settings())
