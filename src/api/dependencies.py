"""FastAPI dependencies for authentication and database access.

This module provides reusable dependencies for:
- Database session management
- JWT token validation
- Current user authentication
- Request metadata extraction
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.database import get_session
from src.models.user import User
from src.services.jwt_service import JWTService, JWTError

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme for JWT authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Get the currently authenticated user from JWT token.

    This dependency validates the JWT access token and returns the
    authenticated user. It should be used on all protected endpoints.

    Args:
        credentials: HTTP Bearer token from Authorization header.
        session: Database session for user lookup.

    Returns:
        Authenticated User model.

    Raises:
        HTTPException: 401 if token invalid, expired, or user not found.

    Example:
        @router.get("/protected")
        async def protected_endpoint(
            current_user: User = Depends(get_current_user)
        ):
            return {"user_id": current_user.id}
    """
    # Extract token from credentials
    token = credentials.credentials

    # Initialize JWT service
    jwt_service = JWTService()

    try:
        # Verify it's an access token (not refresh token) and decode
        jwt_service.verify_token_type(token, "access")

        # Extract user ID from token
        user_id = jwt_service.get_user_id_from_token(token)

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from database
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        logger.warning(f"User {user_id} from token not found in database")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user account is active
    if not user.is_active:
        logger.warning(f"Inactive user {user_id} attempted access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive",
        )

    # Check if user account is locked
    if user.is_locked:
        logger.warning(f"Locked user {user_id} attempted access")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is locked",
        )

    return user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current user and ensure email is verified.

    This dependency adds an additional check that the user's email
    has been verified. Use this for endpoints that require verified users.

    Args:
        current_user: Current authenticated user.

    Returns:
        Authenticated and verified User model.

    Raises:
        HTTPException: 403 if email not verified.

    Example:
        @router.post("/create-provider")
        async def create_provider(
            current_user: User = Depends(get_current_verified_user)
        ):
            # Only verified users can create providers
            pass
    """
    if not current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email verification required",
        )

    return current_user


async def get_optional_current_user(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.

    This dependency is for endpoints that have optional authentication -
    they work for both authenticated and unauthenticated users, but may
    provide different functionality based on authentication status.

    Args:
        request: FastAPI request object.
        session: Database session for user lookup.

    Returns:
        User model if authenticated, None otherwise.

    Example:
        @router.get("/content")
        async def get_content(
            current_user: Optional[User] = Depends(get_optional_current_user)
        ):
            if current_user:
                # Return personalized content
                pass
            else:
                # Return generic content
                pass
    """
    # Check if Authorization header exists
    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    # Extract token
    token = auth_header.replace("Bearer ", "")

    # Initialize JWT service
    jwt_service = JWTService()

    try:
        # Verify it's an access token and get user ID
        jwt_service.verify_token_type(token, "access")
        user_id = jwt_service.get_user_id_from_token(token)

        if not user_id:
            return None

        # Fetch user from database
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user and user.is_active and not user.is_locked:
            return user

    except (JWTError, Exception):
        # Silently fail for optional authentication
        pass

    return None


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP address from request.

    Handles both direct connections and proxy scenarios (X-Forwarded-For).

    Args:
        request: FastAPI request object.

    Returns:
        Client IP address as string, or None if unavailable.

    Example:
        @router.post("/login")
        async def login(
            ip_address: Optional[str] = Depends(get_client_ip)
        ):
            # Log login attempt with IP
            pass
    """
    # Check for X-Forwarded-For header (proxy/load balancer)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take first IP if multiple (client IP)
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return None


def get_user_agent(request: Request) -> Optional[str]:
    """Extract User-Agent header from request.

    Args:
        request: FastAPI request object.

    Returns:
        User-Agent string, or None if not present.

    Example:
        @router.post("/login")
        async def login(
            user_agent: Optional[str] = Depends(get_user_agent)
        ):
            # Log device information
            pass
    """
    return request.headers.get("User-Agent")
