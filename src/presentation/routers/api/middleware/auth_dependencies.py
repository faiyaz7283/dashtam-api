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

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.container import get_cache, get_db_session, get_token_service
from src.core.result import Failure, Success
from src.domain.protocols import CacheProtocol, SessionCache
from src.domain.protocols.token_generation_protocol import TokenGenerationProtocol

if TYPE_CHECKING:
    from src.domain.protocols import SessionRepository

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
        case Success(value=payload):
            # Extract user information from payload
            try:
                # Cast values to expected types (payload is dict[str, str | int | list[str]])
                sub = str(payload["sub"])
                email = str(payload["email"])
                roles_raw = payload.get("roles", ["user"])
                roles = roles_raw if isinstance(roles_raw, list) else ["user"]
                session_id_raw = payload.get("session_id")
                session_id = UUID(str(session_id_raw)) if session_id_raw else None
                jti_raw = payload.get("jti")
                token_jti = str(jti_raw) if jti_raw else None

                return CurrentUser(
                    user_id=UUID(sub),
                    email=email,
                    roles=roles,
                    session_id=session_id,
                    token_jti=token_jti,
                )
            except (KeyError, ValueError) as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token payload",
                    headers={"WWW-Authenticate": "Bearer"},
                ) from e

        case Failure(error=error):
            # Token invalid or expired - error is a string
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error,
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
        case Success(value=payload):
            try:
                # Cast values to expected types (payload is dict[str, str | int | list[str]])
                sub = str(payload["sub"])
                email = str(payload["email"])
                roles_raw = payload.get("roles", ["user"])
                roles = roles_raw if isinstance(roles_raw, list) else ["user"]
                session_id_raw = payload.get("session_id")
                session_id = UUID(str(session_id_raw)) if session_id_raw else None
                jti_raw = payload.get("jti")
                token_jti = str(jti_raw) if jti_raw else None

                return CurrentUser(
                    user_id=UUID(sub),
                    email=email,
                    roles=roles,
                    session_id=session_id,
                    token_jti=token_jti,
                )
            except (KeyError, ValueError):
                return None

        case Failure(error=_):
            return None

    return None  # Explicit return for exhaustiveness


async def get_current_active_user(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    cache: Annotated[CacheProtocol, Depends(get_cache)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CurrentUser:
    """Get current user with session revocation check.

    Security Layer: Verifies JWT is valid AND session is not revoked.
    This prevents post-logout token reuse attacks.

    Flow:
        1. JWT already validated (by get_current_user dependency)
        2. Extract session_id from JWT payload
        3. Check session in Redis cache (fast path <5ms)
        4. If cache miss, check database (slow path ~50ms)
        5. Verify session exists and is NOT revoked
        6. Return 401 if session revoked

    Args:
        current_user: Current user from JWT (already validated).
        cache: Redis cache for fast session lookups.
        session: Database session for fallback lookups.

    Returns:
        CurrentUser if session is valid and not revoked.

    Raises:
        HTTPException 401: If session is revoked or not found.

    Security:
        - Prevents token reuse after logout
        - Prevents token reuse after password change
        - Prevents token reuse after manual session revocation

    Reference:
        - F6.5 Security Audit Item 2: JWT/Refresh Token Security
        - docs/architecture/session-management-architecture.md
    """
    # If no session_id in JWT, allow (backward compatibility)
    # Sessions created before F1.3 may not have session_id
    if current_user.session_id is None:
        return current_user

    # Fast path: Check Redis cache (<5ms)
    from src.infrastructure.cache import RedisSessionCache

    session_cache: SessionCache = RedisSessionCache(cache=cache)
    cached_session = await session_cache.get(current_user.session_id)

    if cached_session is not None:
        # Session found in cache
        if cached_session.is_revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return current_user

    # Slow path: Check database (~50ms)
    from src.infrastructure.persistence.repositories import (
        SessionRepository as SessionRepositoryImpl,
    )

    session_repo: "SessionRepository" = SessionRepositoryImpl(session=session)
    db_session = await session_repo.find_by_id(current_user.session_id)

    if db_session is None:
        # Session not found - token has session_id but session deleted
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if db_session.is_revoked:
        # Session revoked (logout, password change, manual revocation)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Session valid - cache it for future requests
    await session_cache.set(db_session)

    return current_user


def require_role(
    required_role: str,
) -> Callable[..., Awaitable[CurrentUser]]:
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


def require_any_role(
    *required_roles: str,
) -> Callable[..., Awaitable[CurrentUser]]:
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
