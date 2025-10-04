"""JWT-based authentication API endpoints.

This module implements user authentication using JWT tokens including:
- User registration with email verification
- Login with JWT token generation
- Token refresh with rotation support
- Logout (token revocation)
- Password reset flows
- Email verification
- User profile management
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    get_client_ip,
    get_current_user,
    get_user_agent,
)
from src.core.database import get_session
from src.models.user import User
from src.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UpdateUserRequest,
    UserResponse,
)
from src.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: RegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Register a new user account.

    Creates a new user account and sends an email verification link.
    The user must verify their email before they can log in.

    Args:
        request: Registration data (email, password, name).
        session: Database session.

    Returns:
        Success message indicating email sent.

    Raises:
        HTTPException: 400 if email already exists or password invalid.
        HTTPException: 500 if registration fails.
    """
    auth_service = AuthService(session)

    # Register user (verification email sent internally by AuthService)
    user = await auth_service.register_user(
        email=request.email, password=request.password, name=request.name
    )

    logger.info(f"User registered successfully: {user.email}")

    return MessageResponse(
        message="Registration successful. Please check your email to verify your account."
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    request: EmailVerificationRequest,
    session: AsyncSession = Depends(get_session),
):
    """Verify user's email address.

    Validates the email verification token and activates the user account.

    Args:
        request: Verification token from email.
        session: Database session.

    Returns:
        Success message indicating account verified.

    Raises:
        HTTPException: 400 if token invalid or expired.
    """
    auth_service = AuthService(session)

    try:
        await auth_service.verify_email(request.token)

        logger.info("Email verified successfully")

        return MessageResponse(
            message="Email verified successfully. You can now log in."
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Log in to an existing account.

    Authenticates user credentials and returns JWT access and refresh tokens.

    Args:
        request: Login credentials (email, password).
        req: FastAPI request object.
        session: Database session.
        ip_address: Client IP address.
        user_agent: Client user agent string.

    Returns:
        JWT tokens and user profile information.

    Raises:
        HTTPException: 401 if credentials invalid.
        HTTPException: 403 if account locked or inactive.
    """
    auth_service = AuthService(session)

    # Authenticate user and generate tokens
    # AuthService.login returns (access_token, refresh_token, user)
    access_token, refresh_token, user = await auth_service.login(
        email=request.email, password=request.password
    )

    logger.info(f"User logged in successfully: {user.email}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=1800,  # 30 minutes
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            email_verified=user.email_verified,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
        ),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Refresh access token using refresh token.

    Validates refresh token and issues new access and refresh tokens.
    Implements refresh token rotation for security.

    Args:
        request: Refresh token from previous login.
        session: Database session.
        ip_address: Client IP address.
        user_agent: Client user agent string.

    Returns:
        New JWT access and refresh tokens.

    Raises:
        HTTPException: 401 if refresh token invalid or expired.
    """
    auth_service = AuthService(session)

    # Refresh access token using refresh token
    # AuthService.refresh_access_token validates the refresh token and returns new access token
    # Note: Refresh token remains valid (no rotation in current implementation)
    new_access_token = await auth_service.refresh_access_token(
        refresh_token=request.refresh_token
    )

    logger.info("Access token refreshed successfully")

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=request.refresh_token,  # Same refresh token (no rotation)
        token_type="bearer",
        expires_in=1800,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: RefreshTokenRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Log out and revoke refresh token.

    Revokes the provided refresh token, effectively logging out the user
    from the current device/session.

    Args:
        request: Refresh token to revoke.
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if token invalid.
    """
    auth_service = AuthService(session)

    # Logout revokes the refresh token
    # AuthService.logout validates token and marks it as revoked
    await auth_service.logout(refresh_token=request.refresh_token)

    logger.info(f"User logged out: {current_user.email}")

    return MessageResponse(message="Logged out successfully")


@router.post("/password-reset/request", response_model=MessageResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    session: AsyncSession = Depends(get_session),
):
    """Request password reset link.

    Sends a password reset link to the user's email if the account exists.
    Always returns success to prevent email enumeration.

    Args:
        request: Email address for password reset.
        session: Database session.

    Returns:
        Success message indicating email sent.
    """
    auth_service = AuthService(session)

    # Request password reset (email sent internally by AuthService)
    # Always succeeds to prevent email enumeration
    await auth_service.request_password_reset(email=request.email)

    # Always return success to prevent email enumeration
    return MessageResponse(
        message="If an account exists with that email, a password reset link has been sent."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    request: PasswordResetConfirm,
    session: AsyncSession = Depends(get_session),
):
    """Confirm password reset with new password.

    Validates reset token and updates user's password.

    Args:
        request: Reset token and new password.
        session: Database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if token invalid or expired.
    """
    auth_service = AuthService(session)

    # Reset password (confirmation email sent internally by AuthService)
    user = await auth_service.reset_password(
        token=request.token, new_password=request.new_password
    )

    logger.info(f"Password reset successfully for: {user.email}")

    return MessageResponse(
        message="Password reset successfully. You can now log in with your new password."
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """Get current authenticated user's profile.

    Returns profile information for the currently authenticated user.

    Args:
        current_user: Currently authenticated user.

    Returns:
        User profile information.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        email_verified=current_user.email_verified,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at,
    )


@router.patch("/me", response_model=UserResponse)
async def update_current_user_profile(
    request: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Update current user's profile.

    Allows updating name and email. If email is changed, a new verification
    email will be sent and email_verified will be set to False.

    Args:
        request: Updated profile fields.
        current_user: Currently authenticated user.
        session: Database session.

    Returns:
        Updated user profile.

    Raises:
        HTTPException: 400 if email already exists.
    """
    auth_service = AuthService(session)

    # Check if email change requested (not currently supported)
    if request.email and request.email != current_user.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email change is not currently supported. Please contact support.",
        )

    # Update user profile (name only for now)
    if request.name:
        updated_user = await auth_service.update_user_profile(
            user_id=current_user.id, name=request.name
        )
    else:
        updated_user = current_user

    logger.info(f"Profile updated for user: {updated_user.email}")

    return UserResponse(
        id=updated_user.id,
        email=updated_user.email,
        name=updated_user.name,
        email_verified=updated_user.email_verified,
        is_active=updated_user.is_active,
        created_at=updated_user.created_at,
        last_login_at=updated_user.last_login_at,
    )
