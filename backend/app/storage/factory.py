from functools import lru_cache

from app.core.config import Settings, get_settings
from app.storage.base import MediaStorage
from app.storage.local import LocalMediaStorage
from app.storage.supabase import SupabaseMediaStorage


def create_media_storage(settings: Settings) -> MediaStorage:
    if settings.media_storage == "supabase":
        return SupabaseMediaStorage(settings)
    return LocalMediaStorage(settings)


@lru_cache
def get_media_storage() -> MediaStorage:
    return create_media_storage(get_settings())
