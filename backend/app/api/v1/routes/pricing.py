from fastapi import APIRouter

from app.api.dependencies import CurrentUser, PricingServiceDependency
from app.core.errors import error_responses
from app.schemas.catalog import MaterialRate, MaterialRateUpdate

router = APIRouter(tags=["pricing"])


@router.get(
    "/material-rates",
    response_model=list[MaterialRate],
    responses=error_responses(401, 500),
)
def list_material_rates(
    user: CurrentUser,
    service: PricingServiceDependency,
) -> list[MaterialRate]:
    return service.list_material_rates(user)


@router.put(
    "/material-rates/{material}",
    response_model=MaterialRate,
    responses=error_responses(401, 403, 422, 500),
)
def update_material_rate(
    material: str,
    body: MaterialRateUpdate,
    user: CurrentUser,
    service: PricingServiceDependency,
) -> MaterialRate:
    return service.update_material_rate(user, material, body)
