from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, status

from app.api.dependencies import SharingServiceDependency
from app.core.errors import error_responses
from app.schemas.sharing import EnquiryRequest, EnquiryResponse, PublicShareCard

router = APIRouter(tags=["sharing"])


@router.get(
    "/{public_share_id}",
    response_model=PublicShareCard,
    responses=error_responses(404, 422, 500),
)
def get_share_card(
    public_share_id: str,
    service: SharingServiceDependency,
) -> PublicShareCard:
    return service.get_share_card(public_share_id)


@router.post(
    "/{public_share_id}/enquiries",
    response_model=EnquiryResponse,
    status_code=status.HTTP_201_CREATED,
    responses=error_responses(404, 409, 422, 429, 500),
)
def submit_enquiry(
    public_share_id: str,
    body: EnquiryRequest,
    service: SharingServiceDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> EnquiryResponse:
    return service.submit_enquiry(public_share_id, body, str(idempotency_key))
