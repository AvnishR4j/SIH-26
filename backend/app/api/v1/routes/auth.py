from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, status

from app.api.dependencies import AuthServiceDependency
from app.core.errors import error_responses
from app.schemas.auth import (
    RequestOtpRequest,
    RequestOtpResponse,
    VerifyOtpRequest,
    VerifyOtpResponse,
)

router = APIRouter(tags=["authentication"])


@router.post(
    "/request-otp",
    response_model=RequestOtpResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=error_responses(409, 422, 429, 500),
)
def request_otp(
    body: RequestOtpRequest,
    service: AuthServiceDependency,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> RequestOtpResponse:
    return service.request_otp(body.phone, str(idempotency_key))


@router.post(
    "/verify-otp",
    response_model=VerifyOtpResponse,
    responses=error_responses(401, 422, 500),
)
def verify_otp(body: VerifyOtpRequest, service: AuthServiceDependency) -> VerifyOtpResponse:
    return service.verify_otp(body.request_id, body.otp)
