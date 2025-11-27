"""User roles for RBAC authorization.

This enum defines the role hierarchy for the authorization system.
Roles are used with Casbin RBAC to determine user permissions.

Role Hierarchy:
    admin > user > readonly

    - admin: Full system access (inherits user + management capabilities)
    - user: Standard user (inherits readonly + write capabilities)
    - readonly: Read-only access to own resources

Reference:
    - docs/architecture/authorization-architecture.md

Usage:
    from src.domain.enums import UserRole

    # Check role
    if user.role == UserRole.ADMIN:
        # Admin-only logic

    # Assign role via authorization service
    await authz.assign_role(user_id, UserRole.USER)
"""

from enum import Enum


class UserRole(str, Enum):
    """User roles for RBAC authorization.

    Defines the role hierarchy used by Casbin for permission checks.
    Each role inherits permissions from roles below it in hierarchy.

    Hierarchy:
        ADMIN inherits from USER inherits from READONLY

    String Enum:
        Inherits from str for easy serialization and Casbin compatibility.
        Values are lowercase to match Casbin policy format.

    Permissions by Role:
        READONLY:
            - accounts:read
            - transactions:read
            - providers:read
            - sessions:read

        USER (+ readonly permissions):
            - accounts:write
            - transactions:write
            - providers:write
            - sessions:write

        ADMIN (+ user permissions):
            - users:read, users:write
            - admin:read, admin:write
            - security:read, security:write
    """

    ADMIN = "admin"
    """Administrator role with full system access.

    Capabilities:
        - All USER permissions
        - User management (create, deactivate, role assignment)
        - System configuration
        - Security settings (token rotation, etc.)
    """

    USER = "user"
    """Standard user role with read/write access to own resources.

    Capabilities:
        - All READONLY permissions
        - Create/modify own accounts
        - Create/modify own provider connections
        - Manage own sessions
    """

    READONLY = "readonly"
    """Read-only role with view access to own resources.

    Capabilities:
        - View own accounts
        - View own transactions
        - View own provider connections
        - View own sessions

    Use Cases:
        - Shared access (family member viewing)
        - Audit/compliance viewing
        - Temporary restricted access
    """

    @classmethod
    def values(cls) -> list[str]:
        """Get all role values as strings.

        Returns:
            list[str]: List of role values ['admin', 'user', 'readonly'].
        """
        return [role.value for role in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid role.

        Args:
            value: String to check.

        Returns:
            bool: True if value is a valid role.
        """
        return value in cls.values()
