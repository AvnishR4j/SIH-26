from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.dependencies import CurrentUser, SharingServiceDependency
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


@router.delete(
    "/catalogues/{public_share_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(401, 403, 404, 422, 500),
)
def delete_marketplace_catalogue(
    public_share_id: str,
    user: CurrentUser,
    service: SharingServiceDependency,
) -> Response:
    service.delete_marketplace_catalogue(user, public_share_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
