"""JWT authentication dependencies.

FastAPI dependencies for extracting and validating JWT tokens.
Use these dependencies to protect routes that require authentication.

Usage:
    # Protected route (requires auth)
    @router.get("/protected")
    async def protected_route(
        current_user: CurrentUser = Depends(get_current_user),
    ):
        return {"user_id": str(current_user.user_id)}

    # Optional auth route
    @router.get("/optional")
    async def optional_route(
        current_user: CurrentUser | None = Depends(get_current_user_optional),
    ):
        if current_user:
            return {"user_id": str(current_user.user_id)}
        return {"message": "anonymous"}
"""

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.container import get_token_service
from src.core.result import Failure, Success
from src.domain.protocols.token_generation_protocol import TokenGenerationProtocol

# HTTP Bearer token extractor
# auto_error=True returns 401 if no token provided
bearer_scheme = HTTPBearer(auto_error=True)
bearer_scheme_optional = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True, kw_only=True)
class CurrentUser:
    """Authenticated user information from JWT.

    Immutable dataclass containing user identity extracted from JWT token.
    Available as a dependency in protected routes.

    Attributes:
        user_id: User's unique identifier (from JWT 'sub' claim).
        email: User's email address (from JWT 'email' claim).
        roles: User's roles (from JWT 'roles' claim).
        session_id: Session ID if present (from JWT 'session_id' claim).
        token_jti: JWT unique identifier (for token tracking/revocation checks).
    """

    user_id: UUID
    email: str
    roles: list[str]
    session_id: UUID | None = None
    token_jti: str | None = None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    token_service: Annotated[TokenGenerationProtocol, Depends(get_token_service)],
) -> CurrentUser:
    """Get current authenticated user from JWT token.

    FastAPI dependency that extracts and validates the JWT access token
    from the Authorization header and returns the user information.

    Args:
        credentials: Bearer token from Authorization header.
        token_service: JWT token service (injected).

    Returns:
        CurrentUser with user identity from valid JWT.

    Raises:
        HTTPException 401: If token is missing, invalid, or expired.

    Usage:
        @router.get("/protected")
        async def protected_route(
            current_user: CurrentUser = Depends(get_current_user),
        ):
            return {"user_id": str(current_user.user_id)}
    """
    # Validate token
    result = token_service.validate_access_token(credentials.credentials)

    match result:
        case Success(payload):
            # Extract user information from payload
            try:
                return CurrentUser(
                    user_id=UUID(payload["sub"]),
                    email=payload["email"],
                    roles=payload.get("roles", ["user"]),
                    session_id=UUID(payload["session_id"])
                    if payload.get("session_id")
                    else None,
                    token_jti=payload.get("jti"),
                )
            except (KeyError, ValueError) as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e

        case Failure(error):
            # Token invalid or expired
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error.message,
                headers={"WWW-Authenticate": "Bearer"},
            )


async def get_current_user_optional(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(bearer_scheme_optional)
    ],
    token_service: Annotated[TokenGenerationProtocol, Depends(get_token_service)],
) -> CurrentUser | None:
    """Get current user if authenticated, None otherwise.

    FastAPI dependency for routes that work with or without authentication.
    Does not raise errors for missing or invalid tokens.

    Args:
        credentials: Optional Bearer token from Authorization header.
        token_service: JWT token service (injected).

    Returns:
        CurrentUser if valid token provided, None otherwise.

    Usage:
        @router.get("/public-or-private")
        async def route(
            current_user: CurrentUser | None = Depends(get_current_user_optional),
        ):
            if current_user:
                return {"message": f"Hello, {current_user.email}"}
            return {"message": "Hello, anonymous"}
    """
    if credentials is None:
        return None

    result = token_service.validate_access_token(credentials.credentials)

    match result:
        case Success(payload):
            try:
                return CurrentUser(
                    user_id=UUID(payload["sub"]),
                    email=payload["email"],
                    roles=payload.get("roles", ["user"]),
                    session_id=UUID(payload["session_id"])
                    if payload.get("session_id")
                    else None,
                    token_jti=payload.get("jti"),
                )
            except (KeyError, ValueError):
                return None

        case Failure(_):
            return None


async def get_current_active_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """Get current user with active account verification.

    Additional layer that could check if user account is still active.
    For F1.1, this is a pass-through; extend in future for:
    - Database lookup to verify account still active
    - Token revocation check against session store
    - Role-based access control

    Args:
        current_user: Current user from JWT.

    Returns:
        CurrentUser if account is active.

    Raises:
        HTTPException 403: If account is deactivated (future).

    Note:
        Currently pass-through. Extend for session validation in F1.3.
    """
    # Future: Add database lookup to verify user is still active
    # Future: Check token against revocation list
    # For now, JWT validity is sufficient
    return current_user


def require_role(required_role: str):
    """Create a dependency that requires a specific role.

    Factory function that creates a dependency checking for specific role.

    Args:
        required_role: Role required to access the endpoint.

    Returns:
        Dependency function that validates user has required role.

    Usage:
        @router.delete("/admin/users/{id}")
        async def delete_user(
            user_id: UUID,
            current_user: CurrentUser = Depends(require_role("admin")),
        ):
            # Only admins can reach here
            ...

    Raises:
        HTTPException 403: If user does not have required role.
    """

    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if required_role not in current_user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user

    return role_checker


def require_any_role(*required_roles: str):
    """Create a dependency that requires any of the specified roles.

    Args:
        *required_roles: Roles where user must have at least one.

    Returns:
        Dependency function that validates user has at least one role.

    Usage:
        @router.get("/dashboard")
        async def dashboard(
            current_user: CurrentUser = Depends(require_any_role("admin", "manager")),
        ):
            # Admins and managers can access
            ...
    """

    async def role_checker(
        current_user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if not any(role in current_user.roles for role in required_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"One of roles {required_roles} required",
            )
        return current_user

    return role_checker


# Type aliases for cleaner route signatures
AuthenticatedUser = Annotated[CurrentUser, Depends(get_current_user)]
OptionalUser = Annotated[CurrentUser | None, Depends(get_current_user_optional)]
ActiveUser = Annotated[CurrentUser, Depends(get_current_active_user)]
