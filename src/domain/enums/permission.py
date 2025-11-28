"""Permission components for RBAC authorization.

This module defines Resource and Action enums used for permission checks.
Permissions are expressed as resource:action pairs (e.g., "accounts:read").

Reference:
    - docs/architecture/authorization-architecture.md

Usage:
    from src.domain.enums import Resource, Action

    # Permission check
    allowed = await authz.check_permission(
        user_id=user.id,
        resource=Resource.ACCOUNTS,
        action=Action.WRITE,
    )

    # FastAPI dependency
    @router.get("/accounts")
    async def list_accounts(
        _: None = Depends(require_permission(Resource.ACCOUNTS, Action.READ)),
    ):
        ...
"""

from enum import Enum


class Resource(str, Enum):
    """Resources that can be protected by authorization.

    Each resource represents a domain concept that users can access.
    Used with Action enum to form permission checks.

    String Enum:
        Inherits from str for easy serialization and Casbin compatibility.
        Values are lowercase to match Casbin policy format.

    Resource Categories:
        User Domain:
            - ACCOUNTS: Financial accounts
            - TRANSACTIONS: Transaction history
            - PROVIDERS: Brokerage connections
            - SESSIONS: Login sessions

        Admin Domain:
            - USERS: User management
            - ADMIN: Administrative functions
            - SECURITY: Security settings
    """

    # User domain resources
    ACCOUNTS = "accounts"
    """Financial accounts (bank, brokerage, etc.)."""

    TRANSACTIONS = "transactions"
    """Transaction history and details."""

    PROVIDERS = "providers"
    """Brokerage provider connections."""

    SESSIONS = "sessions"
    """User login sessions."""

    # Admin domain resources
    USERS = "users"
    """User management (admin only)."""

    ADMIN = "admin"
    """Administrative functions (admin only)."""

    SECURITY = "security"
    """Security settings like token rotation (admin only)."""

    @classmethod
    def values(cls) -> list[str]:
        """Get all resource values as strings.

        Returns:
            list[str]: List of resource values.
        """
        return [resource.value for resource in cls]


class Action(str, Enum):
    """Actions that can be performed on resources.

    Combined with Resource to form permission checks.
    Currently supports read/write; can be extended for granular control.

    String Enum:
        Inherits from str for easy serialization and Casbin compatibility.
        Values are lowercase to match Casbin policy format.

    Action Semantics:
        READ: View, list, get operations (safe, no side effects)
        WRITE: Create, update, delete operations (modifies state)

    Future Extensions:
        - DELETE: Separate delete permission
        - MANAGE: Full control including delete
        - EXPORT: Data export permission
    """

    READ = "read"
    """View/list access to resource."""

    WRITE = "write"
    """Create/update/delete access to resource."""

    @classmethod
    def values(cls) -> list[str]:
        """Get all action values as strings.

        Returns:
            list[str]: List of action values.
        """
        return [action.value for action in cls]
