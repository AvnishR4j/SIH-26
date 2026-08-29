from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ApiError
from app.services.auth import AuthService, UserRecord, get_auth_service
from app.services.catalog import CatalogService, get_catalog_service
from app.services.media import MediaService, get_media_service

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserRecord:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "UNAUTHORIZED", "A valid bearer token is required.")
    return service.authenticate(credentials.credentials)


CurrentUser = Annotated[UserRecord, Depends(get_current_user)]
AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
CatalogServiceDependency = Annotated[CatalogService, Depends(get_catalog_service)]
MediaServiceDependency = Annotated[MediaService, Depends(get_media_service)]
