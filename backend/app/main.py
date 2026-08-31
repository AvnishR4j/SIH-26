from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.errors import Utf8JSONResponse, install_error_handlers
from app.storage.local import local_media_root


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        default_response_class=Utf8JSONResponse,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(application)
    application.include_router(api_router, prefix=settings.api_prefix)
    if settings.media_storage == "local":
        media_root = local_media_root(settings)
        media_root.mkdir(parents=True, exist_ok=True)
        application.mount("/media", StaticFiles(directory=media_root), name="media")
    return application


app = create_app()
