"""API v1 router aggregation.

This module combines all v1 API routers into a single router
that can be mounted on the main application.
"""

from fastapi import APIRouter

from src.api.v1.provider_types import router as provider_types_router
from src.api.v1.providers import router as providers_router
from src.api.v1.auth import router as auth_oauth_router
from src.api.v1.auth_jwt import router as auth_jwt_router

# Create main API router
api_router = APIRouter()

# Include sub-routers
# Provider types (catalog) - no auth required
api_router.include_router(
    provider_types_router, prefix="/provider-types", tags=["provider-types"]
)

# Provider instances (user connections) - auth required
api_router.include_router(providers_router, prefix="/providers", tags=["providers"])

# OAuth authentication endpoints (provider connections)
api_router.include_router(auth_oauth_router, prefix="/auth", tags=["oauth"])

# JWT authentication endpoints (user auth)
api_router.include_router(auth_jwt_router, prefix="/auth", tags=["authentication"])


# Health check at API level
@api_router.get("/health")
async def api_health():
    """API health check."""
    return {"status": "healthy", "version": "v1"}
