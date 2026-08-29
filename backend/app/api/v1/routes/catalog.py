from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, status

from app.api.dependencies import CatalogServiceDependency, CurrentUser
from app.schemas.catalog import Draft, DraftCreate, DraftList, DraftPatch, DraftStatus

router = APIRouter(tags=["catalogue drafts"])


@router.post("/drafts", response_model=Draft, status_code=status.HTTP_201_CREATED)
def create_draft(
    body: DraftCreate,
    user: CurrentUser,
    service: CatalogServiceDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> Draft:
    return service.create_draft(user, body, str(idempotency_key))


@router.get("/drafts", response_model=DraftList)
def list_drafts(
    user: CurrentUser,
    service: CatalogServiceDependency,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
    status_filter: Annotated[DraftStatus | None, Query(alias="status")] = None,
) -> DraftList:
    return service.list_drafts(user, limit, cursor, status_filter)


@router.get("/drafts/{draft_id}", response_model=Draft)
def get_draft(
    draft_id: str,
    user: CurrentUser,
    service: CatalogServiceDependency,
) -> Draft:
    return service.get_draft(user, draft_id)


@router.patch("/drafts/{draft_id}", response_model=Draft)
def update_draft(
    draft_id: str,
    body: DraftPatch,
    user: CurrentUser,
    service: CatalogServiceDependency,
) -> Draft:
    return service.update_draft(user, draft_id, body)
