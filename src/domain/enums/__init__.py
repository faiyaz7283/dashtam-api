"""Domain enums for business logic.

This package contains enumerations used throughout the domain layer.
Enums are centralized here for discoverability and maintainability.

Following architectural governance (see docs/architecture/directory-structure.md):
- All domain enums live in src/domain/enums/
- Enums are used for type safety and validation
- Keep enums focused and well-documented

Available Enums:
    - AuditAction: Audit trail action types for compliance tracking
    - UserRole: RBAC roles (admin, user, readonly)
    - Resource: Protected resources for authorization
    - Action: Actions on resources (read, write)
"""

from src.domain.enums.audit_action import AuditAction
from src.domain.enums.permission import Action, Resource
from src.domain.enums.rate_limit_scope import RateLimitScope
from src.domain.enums.user_role import UserRole

__all__ = ["AuditAction", "RateLimitScope", "UserRole", "Resource", "Action"]
