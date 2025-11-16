"""Domain enums for business logic.

This package contains enumerations used throughout the domain layer.
Enums are centralized here for discoverability and maintainability.

Following architectural governance (see docs/architecture/directory-structure.md):
- All domain enums live in src/domain/enums/
- Enums are used for type safety and validation
- Keep enums focused and well-documented

Available Enums:
    - AuditAction: Audit trail action types for compliance tracking
"""

from src.domain.enums.audit_action import AuditAction

__all__ = ["AuditAction"]
