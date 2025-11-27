"""API v1 routers.

RESTful resource-based endpoints following strict REST compliance.
All endpoints use resource nouns, not action verbs.

Resources:
    /api/v1/users                  - User management
    /api/v1/sessions               - Session management (login/logout)
    /api/v1/tokens                 - Token management (refresh)
    /api/v1/email-verifications    - Email verification
    /api/v1/password-reset-tokens  - Password reset token requests
    /api/v1/password-resets        - Password reset execution

Admin Resources:
    /api/v1/admin/security/rotations     - Global token rotation
    /api/v1/admin/security/config        - Security configuration
    /api/v1/admin/users/{id}/rotations   - Per-user token rotation
"""

from fastapi import APIRouter

from src.presentation.api.v1.admin import admin_router
from src.presentation.api.v1.email_verifications import (
    router as email_verifications_router,
)
from src.presentation.api.v1.password_resets import (
    password_reset_tokens_router,
    password_resets_router,
)
from src.presentation.api.v1.sessions import router as sessions_router
from src.presentation.api.v1.tokens import router as tokens_router
from src.presentation.api.v1.users import router as users_router

# Create combined v1 router
v1_router = APIRouter(prefix="/api/v1")

# Include all resource routers
v1_router.include_router(users_router)
v1_router.include_router(sessions_router)
v1_router.include_router(tokens_router)
v1_router.include_router(email_verifications_router)
v1_router.include_router(password_reset_tokens_router)
v1_router.include_router(password_resets_router)

# Include admin routers
v1_router.include_router(admin_router)

# Export individual routers for testing
__all__ = [
    "v1_router",
    "users_router",
    "sessions_router",
    "tokens_router",
    "email_verifications_router",
    "password_reset_tokens_router",
    "password_resets_router",
    "admin_router",
]
