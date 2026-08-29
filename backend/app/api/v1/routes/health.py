from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.errors import error_responses
from app.db.session import Database, get_database
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, responses=error_responses(500))
def get_health(
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[Database, Depends(get_database)],
) -> HealthResponse:
    return HealthResponse(
        status="ok" if database.is_available() else "degraded",
        service="kalasetu-api",
        version=settings.app_version,
        environment=settings.environment,
    )
