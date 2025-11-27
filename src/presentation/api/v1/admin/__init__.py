"""Admin API routers.

Admin-only endpoints for security and system management.
All endpoints require admin authentication (TODO: implement admin auth).

Resources:
    /api/v1/admin/security/rotations     - Global token rotation
    /api/v1/admin/security/config        - Security configuration
    /api/v1/admin/users/{id}/rotations   - Per-user token rotation
"""

from fastapi import APIRouter

from src.presentation.api.v1.admin.token_rotation import router as token_rotation_router

# Create combined admin router
admin_router = APIRouter(prefix="/admin", tags=["Admin"])

# Include all admin routers
admin_router.include_router(token_rotation_router)

# Export routers
__all__ = [
    "admin_router",
    "token_rotation_router",
]
