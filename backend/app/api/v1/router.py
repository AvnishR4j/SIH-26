from fastapi import APIRouter

from app.api.v1.routes import auth, catalog, health, profile

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(profile.router)
api_router.include_router(catalog.router, prefix="/catalog")
