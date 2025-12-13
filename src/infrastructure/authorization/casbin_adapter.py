"""Casbin implementation of AuthorizationProtocol.

This adapter provides RBAC authorization using Casbin with:
- AsyncEnforcer for async policy checks
- PostgreSQL adapter for persistent policy storage
- Redis caching for performance (5-min TTL)
- Audit trail for all authorization events
- Domain events for role changes

Following hexagonal architecture:
- Infrastructure implements domain protocol (AuthorizationProtocol)
- Domain doesn't know about Casbin
- Easy to swap implementations (in-memory for testing)

Reference:
    - docs/architecture/authorization-architecture.md
"""

from typing import TYPE_CHECKING
from uuid import UUID

import casbin

from src.core.result import Success
from src.domain.enums import AuditAction
from src.domain.events import (
    RoleAssignmentAttempted,
    RoleAssignmentFailed,
    RoleAssignmentSucceeded,
    RoleRevocationAttempted,
    RoleRevocationFailed,
    RoleRevocationSucceeded,
)

if TYPE_CHECKING:
    from src.domain.protocols.audit_protocol import AuditProtocol
    from src.domain.protocols.cache_protocol import CacheProtocol
    from src.domain.protocols.event_bus_protocol import EventBusProtocol
    from src.domain.protocols.logger_protocol import LoggerProtocol


# Cache key prefix and TTL
CACHE_PREFIX = "authz"
CACHE_TTL_SECONDS = 300  # 5 minutes


class CasbinAdapter:
    """Casbin-based authorization adapter.

    Implements AuthorizationProtocol using Casbin AsyncEnforcer
    with PostgreSQL policy storage and Redis caching.

    Architecture:
        - AsyncEnforcer: Async Casbin enforcer for FastAPI
        - PostgreSQL Adapter: Persistent policy storage (casbin_rule table)
        - Redis Cache: 5-minute TTL for permission results
        - Audit Integration: All checks logged
        - Event Bus: Role changes emit domain events

    Note:
        Enforcer is initialized at FastAPI startup (async required).
        See src/main.py lifespan context manager for initialization.

    Attributes:
        _enforcer: Casbin AsyncEnforcer instance.
        _cache: Redis cache for permission results.
        _audit: Audit adapter for logging authorization checks.
        _event_bus: Event bus for domain events.
        _logger: Structured logger.
    """

    def __init__(
        self,
        enforcer: casbin.AsyncEnforcer,
        cache: "CacheProtocol",
        audit: "AuditProtocol",
        event_bus: "EventBusProtocol",
        logger: "LoggerProtocol",
    ) -> None:
        """Initialize adapter with dependencies.

        Args:
            enforcer: Pre-initialized Casbin AsyncEnforcer.
            cache: Redis cache adapter.
            audit: Audit adapter for logging.
            event_bus: Event bus for domain events.
            logger: Structured logger.
        """
        self._enforcer = enforcer
        self._cache = cache
        self._audit = audit
        self._event_bus = event_bus
        self._logger = logger

    async def check_permission(
        self,
        user_id: UUID,
        resource: str,
        action: str,
    ) -> bool:
        """Check if user has permission for resource/action.

        Checks cache first, then Casbin enforcer. Results are cached
        and all checks are audited.

        Args:
            user_id: User's UUID.
            resource: Resource name (accounts, transactions, users, etc.).
            action: Action name (read, write).

        Returns:
            bool: True if allowed, False if denied.
        """
        cache_key = f"{CACHE_PREFIX}:{user_id}:{resource}:{action}"

        # 1. Check cache first
        cache_result = await self._cache.get(cache_key)
        if isinstance(cache_result, Success) and cache_result.value is not None:
            allowed = cache_result.value == "1"
            self._logger.debug(
                "authorization_cache_hit",
                user_id=str(user_id),
                resource=resource,
                action=action,
                allowed=allowed,
            )
            return allowed

        # 2. Check with Casbin enforcer
        # Note: enforce() is synchronous in Casbin, even with AsyncEnforcer
        user_str = str(user_id)
        try:
            allowed = self._enforcer.enforce(user_str, resource, action)
        except Exception as e:
            # Fail closed on errors
            self._logger.error(
                "authorization_check_error",
                error=e,
                user_id=user_str,
                resource=resource,
                action=action,
            )
            allowed = False

        # 3. Cache result
        await self._cache.set(
            cache_key,
            "1" if allowed else "0",
            ttl=CACHE_TTL_SECONDS,
        )

        # 4. Audit the check
        audit_action = (
            AuditAction.ACCESS_GRANTED if allowed else AuditAction.ACCESS_DENIED
        )
        await self._audit.record(
            action=audit_action,
            resource_type="authorization",
            user_id=user_id,
            context={
                "resource": resource,
                "action": action,
                "allowed": allowed,
                "cached": False,
            },
        )

        # 5. Log the check
        self._logger.info(
            "authorization_check",
            user_id=user_str,
            resource=resource,
            action=action,
            allowed=allowed,
        )

        return allowed

    async def get_roles_for_user(self, user_id: UUID) -> list[str]:
        """Get all roles assigned to user.

        Returns direct roles only (not inherited). Use has_role() to
        check with inheritance.

        Args:
            user_id: User's UUID.

        Returns:
            list[str]: List of role names. Empty if user has no roles.
        """
        user_str = str(user_id)
        try:
            roles = await self._enforcer.get_roles_for_user(user_str)
            return list(roles)
        except Exception as e:
            self._logger.error(
                "get_roles_error",
                error=e,
                user_id=user_str,
            )
            return []

    async def has_role(self, user_id: UUID, role: str) -> bool:
        """Check if user has specific role (including inherited).

        Uses Casbin's role hierarchy to check inheritance.

        Args:
            user_id: User's UUID.
            role: Role name to check.

        Returns:
            bool: True if user has role, False otherwise.
        """
        user_str = str(user_id)
        try:
            result = await self._enforcer.has_role_for_user(user_str, role)
            return bool(result)
        except Exception as e:
            self._logger.error(
                "has_role_error",
                error=e,
                user_id=user_str,
                role=role,
            )
            return False

    async def assign_role(
        self,
        user_id: UUID,
        role: str,
        *,
        assigned_by: UUID,
    ) -> bool:
        """Assign role to user.

        Emits domain events and invalidates permission cache.

        Args:
            user_id: User's UUID to assign role to.
            role: Role name to assign.
            assigned_by: UUID of user performing the assignment.

        Returns:
            bool: True if role assigned, False if user already had role.
        """
        user_str = str(user_id)

        # 1. Emit attempt event
        await self._event_bus.publish(
            RoleAssignmentAttempted(
                user_id=user_id,
                role=role,
                assigned_by=assigned_by,
            )
        )

        # 2. Check if already has role
        if await self.has_role(user_id, role):
            await self._event_bus.publish(
                RoleAssignmentFailed(
                    user_id=user_id,
                    role=role,
                    assigned_by=assigned_by,
                    reason="already_has_role",
                )
            )
            return False

        # 3. Assign role via Casbin
        try:
            await self._enforcer.add_role_for_user(user_str, role)
            await self._enforcer.save_policy()
        except Exception as e:
            self._logger.error(
                "assign_role_error",
                error=e,
                user_id=user_str,
                role=role,
            )
            await self._event_bus.publish(
                RoleAssignmentFailed(
                    user_id=user_id,
                    role=role,
                    assigned_by=assigned_by,
                    reason=f"database_error: {str(e)}",
                )
            )
            return False

        # 4. Invalidate user's permission cache
        await self._invalidate_user_cache(user_id)

        # 5. Emit success event
        await self._event_bus.publish(
            RoleAssignmentSucceeded(
                user_id=user_id,
                role=role,
                assigned_by=assigned_by,
            )
        )

        self._logger.info(
            "role_assigned",
            user_id=user_str,
            role=role,
            assigned_by=str(assigned_by),
        )

        return True

    async def revoke_role(
        self,
        user_id: UUID,
        role: str,
        *,
        revoked_by: UUID,
        reason: str | None = None,
    ) -> bool:
        """Revoke role from user.

        Emits domain events and invalidates permission cache.

        Args:
            user_id: User's UUID to revoke role from.
            role: Role name to revoke.
            revoked_by: UUID of user performing the revocation.
            reason: Optional reason for revocation.

        Returns:
            bool: True if role revoked, False if user didn't have role.
        """
        user_str = str(user_id)

        # 1. Emit attempt event
        await self._event_bus.publish(
            RoleRevocationAttempted(
                user_id=user_id,
                role=role,
                revoked_by=revoked_by,
                reason=reason,
            )
        )

        # 2. Check if has role
        if not await self.has_role(user_id, role):
            await self._event_bus.publish(
                RoleRevocationFailed(
                    user_id=user_id,
                    role=role,
                    revoked_by=revoked_by,
                    reason="does_not_have_role",
                )
            )
            return False

        # 3. Revoke role via Casbin
        try:
            await self._enforcer.delete_role_for_user(user_str, role)
            await self._enforcer.save_policy()
        except Exception as e:
            self._logger.error(
                "revoke_role_error",
                error=e,
                user_id=user_str,
                role=role,
            )
            await self._event_bus.publish(
                RoleRevocationFailed(
                    user_id=user_id,
                    role=role,
                    revoked_by=revoked_by,
                    reason=f"database_error: {str(e)}",
                )
            )
            return False

        # 4. Invalidate user's permission cache
        await self._invalidate_user_cache(user_id)

        # 5. Emit success event
        await self._event_bus.publish(
            RoleRevocationSucceeded(
                user_id=user_id,
                role=role,
                revoked_by=revoked_by,
                reason=reason,
            )
        )

        self._logger.info(
            "role_revoked",
            user_id=user_str,
            role=role,
            revoked_by=str(revoked_by),
            reason=reason,
        )

        return True

    async def get_permissions_for_role(self, role: str) -> list[tuple[str, str]]:
        """Get all permissions for a role.

        Returns direct permissions (not inherited).

        Args:
            role: Role name.

        Returns:
            list[tuple[str, str]]: List of (resource, action) tuples.
        """
        try:
            # Casbin returns list of [role, resource, action] lists
            policies = await self._enforcer.get_permissions_for_user(role)
            return [(p[1], p[2]) for p in policies if len(p) >= 3]
        except Exception as e:
            self._logger.error(
                "get_permissions_error",
                error=e,
                role=role,
            )
            return []

    async def _invalidate_user_cache(self, user_id: UUID) -> None:
        """Invalidate all cached permissions for user.

        Called after role changes to ensure fresh permission checks.

        Args:
            user_id: User whose cache should be invalidated.
        """
        pattern = f"{CACHE_PREFIX}:{user_id}:*"
        try:
            await self._cache.delete_pattern(pattern)
            self._logger.debug(
                "cache_invalidated",
                user_id=str(user_id),
                pattern=pattern,
            )
        except Exception as e:
            # Log but don't fail - cache miss is safe
            self._logger.warning(
                "cache_invalidation_error",
                user_id=str(user_id),
                error=str(e),
            )
