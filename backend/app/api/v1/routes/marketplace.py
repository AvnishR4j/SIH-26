from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import SharingServiceDependency
from app.core.errors import error_responses
from app.schemas.sharing import MarketplaceCataloguePage

router = APIRouter(tags=["marketplace"])


@router.get(
    "/catalogues",
    response_model=MarketplaceCataloguePage,
    responses=error_responses(422, 500),
)
def list_marketplace_catalogues(
    service: SharingServiceDependency,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: str | None = None,
) -> MarketplaceCataloguePage:
    return service.list_marketplace_catalogues(limit, cursor)
