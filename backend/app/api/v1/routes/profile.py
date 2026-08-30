from fastapi import APIRouter

from app.api.dependencies import AuthServiceDependency, CurrentUser
from app.core.errors import error_responses
from app.schemas.profile import (
    ConsentStatus,
    MediaConsentRequest,
    ProfileResponse,
    ProfileUpdate,
)

router = APIRouter(tags=["profile"])


@router.get("/me", response_model=ProfileResponse, responses=error_responses(401, 500))
def get_profile(user: CurrentUser, service: AuthServiceDependency) -> ProfileResponse:
    return service.profile(user)


@router.patch(
    "/me",
    response_model=ProfileResponse,
    responses=error_responses(401, 422, 500),
)
def update_profile(
    body: ProfileUpdate,
    user: CurrentUser,
    service: AuthServiceDependency,
) -> ProfileResponse:
    return service.update_profile(user, body)


@router.put(
    "/me/consents/media-processing",
    response_model=ConsentStatus,
    responses=error_responses(401, 422, 500),
)
def update_media_consent(
    body: MediaConsentRequest,
    user: CurrentUser,
    service: AuthServiceDependency,
) -> ConsentStatus:
    return service.update_consent(user, body.accepted, body.policy_version)
