"""Admin API handlers.

Handler functions for admin security and system management endpoints.
Routes are registered via ROUTE_REGISTRY in routes/registry.py.
All handlers require admin authentication (Casbin RBAC).

Handlers:
    create_global_rotation - Global token rotation
    create_user_rotation   - Per-user token rotation
    get_security_config    - Security configuration
"""

from src.presentation.routers.api.v1.admin.token_rotation import (
    create_global_rotation,
    create_user_rotation,
    get_security_config,
)

# Export handlers
__all__ = [
    "create_global_rotation",
    "create_user_rotation",
    "get_security_config",
]
