from pathlib import PurePosixPath
from typing import Protocol

from app.core.errors import ApiError


class MediaStorage(Protocol):
    def is_available(self) -> bool: ...

    def save(self, key: str, content: bytes) -> None: ...

    def read(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def url(self, key: str) -> str: ...


def normalized_media_key(key: str) -> str:
    path = PurePosixPath(key)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ApiError(500, "INTERNAL_ERROR", "The media key is invalid.")
    return path.as_posix()
