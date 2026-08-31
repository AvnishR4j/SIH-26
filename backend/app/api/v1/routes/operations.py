from fastapi import APIRouter

from app.api.dependencies import CurrentUser, MediaServiceDependency
from app.core.errors import error_responses
from app.schemas.operations import OperationResponse

router = APIRouter(tags=["operations"])


@router.get(
    "/{operation_id}",
    response_model=OperationResponse,
    responses=error_responses(401, 404, 500),
)
def get_operation(
    operation_id: str,
    user: CurrentUser,
    service: MediaServiceDependency,
) -> OperationResponse:
    return service.get_operation(user, operation_id)
