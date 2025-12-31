"""API v1 routers.

RESTful resource-based endpoints following strict REST compliance.
All endpoints use resource nouns, not action verbs.

NOTE: All routes are now generated from the Route Metadata Registry at startup.
The registry (ROUTE_REGISTRY) is the single source of truth for all endpoints.
See src/presentation/routers/api/v1/routes/registry.py for the complete route catalog.

Resources:
    /api/v1/users                  - User management
    /api/v1/sessions               - Session management (login/logout)
    /api/v1/tokens                 - Token management (refresh)
    /api/v1/email-verifications    - Email verification
    /api/v1/password-reset-tokens  - Password reset token requests
    /api/v1/password-resets        - Password reset execution
    /api/v1/providers              - Provider connection management
    /api/v1/accounts               - Account management
    /api/v1/transactions           - Transaction management
    /api/v1/holdings               - Holdings management
    /api/v1/balance-snapshots      - Balance snapshot management
    /api/v1/imports                - File-based data imports

Admin Resources:
    /api/v1/admin/security/rotations     - Global token rotation
    /api/v1/admin/security/config        - Security configuration
    /api/v1/admin/users/{id}/rotations   - Per-user token rotation

Reference:
    - docs/architecture/registry-pattern-architecture.md
"""

from fastapi import APIRouter

from src.presentation.routers.api.v1.routes.generator import (
    register_routes_from_registry,
)
from src.presentation.routers.api.v1.routes.registry import ROUTE_REGISTRY

# Create v1 router and generate all routes from registry
v1_router = APIRouter(prefix="/api/v1")
register_routes_from_registry(v1_router, ROUTE_REGISTRY)

# Export v1_router
__all__ = [
    "v1_router",
]
