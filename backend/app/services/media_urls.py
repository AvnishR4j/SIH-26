from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import MediaObject
from app.schemas.catalog import Draft, DraftImage
from app.storage.base import MediaStorage


def refresh_draft_image_urls(
    session: Session,
    draft: Draft,
    storage: MediaStorage,
) -> Draft:
    if not draft.images:
        return draft
    media_by_id = {
        media.id: media
        for media in session.scalars(
            select(MediaObject).where(
                MediaObject.draft_id == draft.id,
                MediaObject.id.in_([image.id for image in draft.images]),
            )
        )
    }
    return draft.model_copy(
        update={
            "images": [
                refresh_image_urls(image, media_by_id.get(image.id), storage)
                for image in draft.images
            ]
        }
    )


def refresh_image_urls(
    image: DraftImage,
    media: MediaObject | None,
    storage: MediaStorage,
) -> DraftImage:
    if media is None:
        return image
    return image.model_copy(
        update={
            "original_url": storage.url(media.original_key),
            "enhanced_url": storage.url(media.enhanced_key) if media.enhanced_key else None,
        }
    )
