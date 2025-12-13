"""Authorization protocol (port) for RBAC access control.

This protocol defines the contract for authorization systems. Infrastructure adapters
implement this protocol to provide concrete authorization (Casbin, custom RBAC, etc.).

Following hexagonal architecture:
- Domain defines the PORT (this protocol)
- Infrastructure provides ADAPTERS (CasbinAdapter)
- Application layer uses the protocol (doesn't know about Casbin)

Reference:
    - docs/architecture/authorization-architecture.md

Usage:
    from src.domain.protocols import AuthorizationProtocol

    # Dependency injection via container
    authz: AuthorizationProtocol = Depends(get_authorization)

    # Check permission
    allowed = await authz.check_permission(
        user_id=user.id,
        resource="accounts",
        action="write",
    )

    # Get user roles
    roles = await authz.get_roles_for_user(user.id)

    # Assign role
    await authz.assign_role(user.id, "admin", assigned_by=admin.id)
"""

from typing import Protocol
from uuid import UUID


class AuthorizationProtocol(Protocol):
    """Protocol for authorization systems.

    Provides RBAC (Role-Based Access Control) operations including permission
    checks, role management, and role queries.

    Implementations:
        - CasbinAdapter: Production (Casbin + PostgreSQL)
        - InMemoryAuthorizationAdapter: Testing

    Security:
        - All permission checks are audited
        - Role changes emit domain events
        - Cache invalidation on role changes

    Error Handling:
        Permission checks return bool (fail-closed design).
        Role operations return bool (success/failure).
        Exceptions are logged but don't bubble up (fail-closed).
    """

    async def check_permission(
        self,
        user_id: UUID,
        resource: str,
        action: str,
    ) -> bool:
        """Check if user has permission for resource/action.

        Core authorization method. Checks Casbin policies including role
        inheritance. Results are cached for performance.

        Args:
            user_id: User's UUID.
            resource: Resource name (accounts, transactions, users, etc.).
            action: Action name (read, write).

        Returns:
            bool: True if allowed, False if denied.

        Side Effects:
            - Audits the authorization check (ACCESS_GRANTED/ACCESS_DENIED)
            - Caches result in Redis (5 min TTL)

        Example:
            allowed = await authz.check_permission(
                user_id=user.id,
                resource="accounts",
                action="write",
            )
            if not allowed:
                raise HTTPException(403, "Permission denied")
        """
        ...

    async def get_roles_for_user(self, user_id: UUID) -> list[str]:
        """Get all roles assigned to user (including inherited).

        Returns the role hierarchy. For example, if user has 'admin' role,
        returns ['admin', 'user', 'readonly'] due to inheritance.

        Args:
            user_id: User's UUID.

        Returns:
            list[str]: List of role names. Empty if user has no roles.

        Example:
            roles = await authz.get_roles_for_user(user.id)
            # ['admin', 'user', 'readonly'] for admin user
        """
        ...

    async def has_role(self, user_id: UUID, role: str) -> bool:
        """Check if user has specific role (including inherited).

        Considers role hierarchy. Admin inherits user, user inherits readonly.

        Args:
            user_id: User's UUID.
            role: Role name to check (admin, user, readonly).

        Returns:
            bool: True if user has role, False otherwise.

        Example:
            # Admin has all roles due to inheritance
            await authz.has_role(admin_user.id, "readonly")  # True
            await authz.has_role(admin_user.id, "admin")     # True
        """
        ...

    async def assign_role(
        self,
        user_id: UUID,
        role: str,
        *,
        assigned_by: UUID,
    ) -> bool:
        """Assign role to user.

        Adds user to role. Emits domain events and invalidates permission cache.

        Args:
            user_id: User's UUID to assign role to.
            role: Role name to assign (admin, user, readonly).
            assigned_by: UUID of user performing the assignment (for audit).

        Returns:
            bool: True if role assigned, False if user already had role.

        Side Effects:
            - Emits RoleAssignmentAttempted event (before)
            - Emits RoleAssignmentSucceeded/Failed event (after)
            - Invalidates user's permission cache
            - Audits the role assignment

        Example:
            success = await authz.assign_role(
                user_id=target_user.id,
                role="admin",
                assigned_by=admin.id,
            )
        """
        ...

    async def revoke_role(
        self,
        user_id: UUID,
        role: str,
        *,
        revoked_by: UUID,
        reason: str | None = None,
    ) -> bool:
        """Revoke role from user.

        Removes user from role. Emits domain events and invalidates cache.

        Args:
            user_id: User's UUID to revoke role from.
            role: Role name to revoke (admin, user, readonly).
            revoked_by: UUID of user performing the revocation (for audit).
            reason: Optional reason for revocation (for audit trail).

        Returns:
            bool: True if role revoked, False if user didn't have role.

        Side Effects:
            - Emits RoleRevocationAttempted event (before)
            - Emits RoleRevocationSucceeded/Failed event (after)
            - Invalidates user's permission cache
            - Audits the role revocation
            - May revoke sessions if admin role removed

        Example:
            success = await authz.revoke_role(
                user_id=target_user.id,
                role="admin",
                revoked_by=admin.id,
                reason="User left admin team",
            )
        """
        ...

    async def get_permissions_for_role(self, role: str) -> list[tuple[str, str]]:
        """Get all permissions for a role.

        Returns direct permissions (not inherited). Useful for admin UI.

        Args:
            role: Role name (admin, user, readonly).

        Returns:
            list[tuple[str, str]]: List of (resource, action) tuples.

        Example:
            perms = await authz.get_permissions_for_role("user")
            # [("accounts", "write"), ("transactions", "write"), ...]
        """
        ...
