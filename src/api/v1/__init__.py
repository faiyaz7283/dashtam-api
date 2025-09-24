"""API v1 router aggregation.

This module combines all v1 API routers into a single router
that can be mounted on the main application.
"""

from fastapi import APIRouter

from src.api.v1.providers import router as providers_router
from src.api.v1.auth import router as auth_router

# Create main API router
api_router = APIRouter()

# Include sub-routers
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])

api_router.include_router(auth_router, prefix="/auth", tags=["authentication"])


# Health check at API level
@api_router.get("/health")
async def api_health():
    """API health check."""
    return {"status": "healthy", "version": "v1"}
