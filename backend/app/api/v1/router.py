from fastapi import APIRouter

from app.api.v1.routes import (
    auth,
    catalog,
    health,
    marketplace,
    operations,
    pricing,
    profile,
    sharing,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(profile.router)
api_router.include_router(catalog.router, prefix="/catalog")
api_router.include_router(pricing.router, prefix="/pricing")
api_router.include_router(marketplace.router, prefix="/marketplace")
api_router.include_router(operations.router, prefix="/operations")
api_router.include_router(sharing.router, prefix="/share")
