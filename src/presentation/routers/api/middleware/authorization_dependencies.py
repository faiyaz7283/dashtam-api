"""Casbin authorization dependencies.

FastAPI dependencies for checking permissions using Casbin RBAC.
Use these dependencies in addition to JWT authentication for
fine-grained access control.

Architecture:
    - JWT Authentication (auth_dependencies.py): Verifies user identity
    - Casbin Authorization (this file): Verifies user permissions

Usage:
    # Permission-protected route
    @router.get("/accounts")
    async def list_accounts(
        current_user: CurrentUser = Depends(get_current_user),
        _: None = Depends(require_permission("accounts", "read")),
    ):
        return {"accounts": [...]}

    # Admin-only route (uses Casbin role check)
    @router.post("/admin/users")
    async def create_admin_user(
        current_user: CurrentUser = Depends(get_current_user),
        _: None = Depends(require_casbin_role("admin")),
    ):
        return {"message": "Admin created"}

Reference:
    - docs/architecture/authorization-architecture.md
"""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from src.core.container import get_authorization
from src.domain.protocols.authorization_protocol import AuthorizationProtocol
from src.presentation.routers.api.middleware.auth_dependencies import (
    CurrentUser,
    get_current_user,
)


def require_permission(
    resource: str,
    action: str,
) -> Callable[..., Awaitable[None]]:
    """Create a dependency that requires specific permission.

    Uses Casbin RBAC to check if user has permission for resource/action.
    Permission is checked against user's roles (from JWT) via Casbin enforcer.

    Args:
        resource: Resource name (accounts, transactions, users, etc.).
        action: Action name (read, write).

    Returns:
        Dependency function that validates user has required permission.

    Usage:
        @router.get("/accounts")
        async def list_accounts(
            current_user: CurrentUser = Depends(get_current_user),
            _: None = Depends(require_permission("accounts", "read")),
        ):
            ...

    Raises:
        HTTPException 403: If user does not have required permission.

    Note:
        Permission check uses Casbin enforcer which:
        - Checks cache first (5-minute TTL)
        - Falls back to database if cache miss
        - Audits all checks (ACCESS_GRANTED/ACCESS_DENIED)
    """

    async def permission_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
        authorization: Annotated[AuthorizationProtocol, Depends(get_authorization)],
    ) -> None:
        # Check permission via Casbin
        allowed = await authorization.check_permission(
            user_id=current_user.user_id,
            resource=resource,
            action=action,
        )

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {resource}:{action}",
            )

    return permission_checker


def require_casbin_role(
    role: str,
) -> Callable[..., Awaitable[None]]:
    """Create a dependency that requires specific role (via Casbin).

    Unlike require_role() in auth_dependencies.py which only checks JWT,
    this verifies role assignment against Casbin database. Use this when
    you need real-time role verification (role may have been revoked).

    Args:
        role: Role name required (admin, user, readonly).

    Returns:
        Dependency function that validates user has required role.

    Usage:
        @router.post("/admin/rotate-tokens")
        async def rotate_tokens(
            current_user: CurrentUser = Depends(get_current_user),
            _: None = Depends(require_casbin_role("admin")),
        ):
            # Real-time role check against database
            ...

    Raises:
        HTTPException 403: If user does not have required role.

    Note:
        - JWT role check (auth_dependencies.require_role) is faster but
          may be stale if role was revoked after token issuance.
        - Casbin role check (this function) queries database but ensures
          role assignment is current.
        - Use JWT check for most routes, Casbin check for sensitive operations.
    """

    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
        authorization: Annotated[AuthorizationProtocol, Depends(get_authorization)],
    ) -> None:
        # Check role via Casbin (real-time database check)
        has_role = await authorization.has_role(
            user_id=current_user.user_id,
            role=role,
        )

        if not has_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' required",
            )

    return role_checker


def require_any_permission(
    *permissions: tuple[str, str],
) -> Callable[..., Awaitable[None]]:
    """Create a dependency that requires any of the specified permissions.

    User must have at least one of the specified permissions.

    Args:
        *permissions: Tuples of (resource, action) where user needs at least one.

    Returns:
        Dependency function that validates user has at least one permission.

    Usage:
        @router.get("/reports")
        async def get_reports(
            current_user: CurrentUser = Depends(get_current_user),
            _: None = Depends(require_any_permission(
                ("accounts", "read"),
                ("transactions", "read"),
            )),
        ):
            # User can read accounts OR transactions
            ...

    Raises:
        HTTPException 403: If user has none of the required permissions.
    """

    async def permission_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
        authorization: Annotated[AuthorizationProtocol, Depends(get_authorization)],
    ) -> None:
        for resource, action in permissions:
            allowed = await authorization.check_permission(
                user_id=current_user.user_id,
                resource=resource,
                action=action,
            )
            if allowed:
                return  # At least one permission granted

        # Format permissions for error message
        perms_str = ", ".join(f"{r}:{a}" for r, a in permissions)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: requires one of [{perms_str}]",
        )

    return permission_checker


def require_all_permissions(
    *permissions: tuple[str, str],
) -> Callable[..., Awaitable[None]]:
    """Create a dependency that requires all specified permissions.

    User must have ALL of the specified permissions.

    Args:
        *permissions: Tuples of (resource, action) where user needs all.

    Returns:
        Dependency function that validates user has all permissions.

    Usage:
        @router.post("/accounts/{id}/transfer")
        async def transfer_funds(
            current_user: CurrentUser = Depends(get_current_user),
            _: None = Depends(require_all_permissions(
                ("accounts", "read"),
                ("accounts", "write"),
                ("transactions", "write"),
            )),
        ):
            # User must have all three permissions
            ...

    Raises:
        HTTPException 403: If user is missing any required permission.
    """

    async def permission_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
        authorization: Annotated[AuthorizationProtocol, Depends(get_authorization)],
    ) -> None:
        for resource, action in permissions:
            allowed = await authorization.check_permission(
                user_id=current_user.user_id,
                resource=resource,
                action=action,
            )
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied: {resource}:{action}",
                )

    return permission_checker
