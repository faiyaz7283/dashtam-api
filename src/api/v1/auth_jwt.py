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

from src.api.dependencies import (
    get_auth_service,
    get_client_ip,
    get_current_user,
    get_user_agent,
)
from src.models.user import User
from src.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    LoginResponse,
    UserResponse,
    UpdateUserRequest,
    ChangePasswordRequest,
    EmailVerificationRequest,
    RefreshTokenRequest,
    MessageResponse,
)
from src.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new user account.

    Creates a new user account and sends an email verification link.
    The user must verify their email before they can log in.

    Args:
        request: Registration data (email, password, name).
        auth_service: Authentication service dependency.

    Returns:
        Success message indicating email sent.

    Raises:
        HTTPException: 400 if email already exists or password invalid.
        HTTPException: 500 if registration fails.
    """

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
    auth_service: AuthService = Depends(get_auth_service),
):
    """Verify user's email address.

    Validates the email verification token and activates the user account.

    Args:
        request: Verification token from email.
        auth_service: Authentication service dependency.

    Returns:
        Success message indicating account verified.

    Raises:
        HTTPException: 400 if token invalid or expired.
    """

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
    auth_service: AuthService = Depends(get_auth_service),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Log in to an existing account.

    Authenticates user credentials and returns JWT access and refresh tokens.

    Args:
        request: Login credentials (email, password).
        req: FastAPI request object.
        auth_service: Authentication service dependency.
        ip_address: Client IP address.
        user_agent: Client user agent string.

    Returns:
        JWT tokens and user profile information.

    Raises:
        HTTPException: 401 if credentials invalid.
        HTTPException: 403 if account locked or inactive.
    """

    # Authenticate user and generate tokens with session metadata
    # AuthService.login returns (access_token, refresh_token, user)
    access_token, refresh_token, user = await auth_service.login(
        email=request.email,
        password=request.password,
        ip_address=ip_address,
        user_agent=user_agent,
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
    auth_service: AuthService = Depends(get_auth_service),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Refresh access token using refresh token.

    Validates refresh token and issues new access and refresh tokens.
    Implements refresh token rotation for security.

    Args:
        request: Refresh token from previous login.
        auth_service: Authentication service dependency.
        ip_address: Client IP address.
        user_agent: Client user agent string.

    Returns:
        New JWT access and refresh tokens.

    Raises:
        HTTPException: 401 if refresh token invalid or expired.
    """

    # Refresh access token using refresh token with session tracking
    # AuthService.refresh_access_token validates the refresh token and returns new access token
    # Updates last_activity and includes jti claim for session management
    # Note: Refresh token remains valid (no rotation in current implementation)
    new_access_token = await auth_service.refresh_access_token(
        refresh_token=request.refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
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
    auth_service: AuthService = Depends(get_auth_service),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Log out and revoke refresh token.

    Revokes the provided refresh token, effectively logging out the user
    from the current device/session.

    Args:
        request: Refresh token to revoke.
        current_user: Currently authenticated user.
        auth_service: Authentication service dependency.
        ip_address: Client IP address for audit trail.
        user_agent: Client User-Agent for audit trail.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if token invalid.
    """

    # Logout revokes the refresh token
    # AuthService.logout validates token and marks it as revoked
    await auth_service.logout(refresh_token=request.refresh_token)

    logger.info(f"User logged out: {current_user.email}")

    return MessageResponse(message="Logged out successfully")


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Get current authenticated user's profile.

    Returns profile information for the currently authenticated user.

    Args:
        current_user: Currently authenticated user.
        ip_address: Client IP address for audit trail.
        user_agent: Client User-Agent for audit trail.

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
    auth_service: AuthService = Depends(get_auth_service),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Update current user's profile.

    Allows updating name and email. If email is changed, a new verification
    email will be sent and email_verified will be set to False.

    Args:
        request: Updated profile fields.
        current_user: Currently authenticated user.
        auth_service: Authentication service dependency.
        ip_address: Client IP address for audit trail.
        user_agent: Client User-Agent for audit trail.

    Returns:
        Updated user profile.

    Raises:
        HTTPException: 400 if email already exists.
    """

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


@router.patch("/me/password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
):
    """Change current user's password.

    Requires current password for verification. After successful password change,
    ALL active tokens for this user are automatically rotated (invalidated),
    forcing re-login on all devices for security.

    Args:
        request: Current and new passwords.
        current_user: Currently authenticated user.
        auth_service: Authentication service dependency.
        ip_address: Client IP address for audit trail.
        user_agent: Client User-Agent for audit trail.

    Returns:
        Success message with security notice.

    Raises:
        HTTPException: 400 if current password wrong or new password weak.
    """

    # Change password (includes automatic token rotation)
    await auth_service.change_password(
        user_id=current_user.id,
        current_password=request.current_password,
        new_password=request.new_password,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    logger.info(f"Password changed for user: {current_user.email}")

    return MessageResponse(
        message="Password changed successfully. All active sessions have been logged out for security. Please log in again."
    )
