from typing import Annotated

from fastapi import APIRouter, Header, status

from app.api.dependencies import AuthServiceDependency
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
)
def request_otp(
    body: RequestOtpRequest,
    service: AuthServiceDependency,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
) -> RequestOtpResponse:
    return service.request_otp(body.phone, idempotency_key)


@router.post("/verify-otp", response_model=VerifyOtpResponse)
def verify_otp(body: VerifyOtpRequest, service: AuthServiceDependency) -> VerifyOtpResponse:
    return service.verify_otp(body.request_id, body.otp)
