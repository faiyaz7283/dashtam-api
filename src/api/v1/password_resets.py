"""Password reset API endpoints (resource-oriented design).

This module implements password reset functionality as a RESTful resource:
- POST /password-resets: Create a password reset request
- GET /password-resets/{token}: Verify a reset token
- PATCH /password-resets/{token}: Complete the password reset

This design is more REST-compliant than action-oriented URLs like
/password-reset/request and /password-reset/confirm.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_client_ip, get_user_agent
from src.core.database import get_session
from src.schemas.auth import (
    CompletePasswordResetRequest,
    CreatePasswordResetRequest,
    VerifyResetTokenResponse,
)
from src.schemas.common import MessageResponse
from src.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()

# Endpoints


@router.post("/", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_password_reset(
    request: CreatePasswordResetRequest,
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """Request a password reset link.

    Sends a password reset email if the account exists.
    Always returns success to prevent email enumeration.

    Args:
        request: Email address for password reset.
        session: Database session.

    Returns:
        Success message indicating email sent (whether account exists or not).
    """
    auth_service = AuthService(session)

    # Request password reset (email sent internally by AuthService)
    # Always succeeds to prevent email enumeration
    await auth_service.request_password_reset(email=request.email)

    logger.info("Password reset requested for email (enumeration protected)")

    return MessageResponse(
        message="If an account exists with that email, a password reset link has been sent."
    )


@router.get("/{token}", response_model=VerifyResetTokenResponse)
async def verify_reset_token(
    token: str,
    session: AsyncSession = Depends(get_session),
) -> VerifyResetTokenResponse:
    """Verify that a password reset token is valid.

    Optional endpoint to check token validity before showing password form.
    Useful for better UX (show error immediately if token expired/invalid).

    Args:
        token: Password reset token from email.
        session: Database session.

    Returns:
        Token validity information.
    """
    try:
        # Get all unused reset tokens for potential match (same pattern as reset_password)
        from src.models.auth import PasswordResetToken
        from src.models.user import User
        from src.services.password_service import PasswordService
        from sqlmodel import select

        # Get all unused password reset tokens
        result = await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.used_at.is_(None))
        )
        reset_tokens = result.scalars().all()

        # Find matching token by comparing hashes (bcrypt comparison)
        password_service = PasswordService()
        reset_token = None
        for token_record in reset_tokens:
            if password_service.verify_password(token, token_record.token_hash):
                reset_token = token_record
                break

        if not reset_token or not reset_token.is_valid:
            return VerifyResetTokenResponse(valid=False)

        # Get user email
        result = await session.execute(
            select(User).where(User.id == reset_token.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return VerifyResetTokenResponse(valid=False)

        logger.info(f"Password reset token verified for user: {user.email}")

        return VerifyResetTokenResponse(
            valid=True,
            email=user.email,
            expires_at=reset_token.expires_at.isoformat()
            if reset_token.expires_at
            else None,
        )

    except Exception as e:
        logger.error(f"Error verifying password reset token: {e}")
        return VerifyResetTokenResponse(valid=False)


@router.patch("/{token}", response_model=MessageResponse)
async def complete_password_reset(
    token: str,
    request: CompletePasswordResetRequest,
    session: AsyncSession = Depends(get_session),
    ip_address: Optional[str] = Depends(get_client_ip),
    user_agent: Optional[str] = Depends(get_user_agent),
) -> MessageResponse:
    """Complete password reset with new password.

    Validates the token and updates the user's password.

    Args:
        token: Password reset token from email.
        request: New password.
        session: Database session.
        ip_address: Client IP address for audit trail.
        user_agent: Client User-Agent for audit trail.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if token invalid or expired, or password weak.
    """
    auth_service = AuthService(session)

    try:
        # Reset password (confirmation email sent internally by AuthService)
        user = await auth_service.reset_password(
            token=token,
            new_password=request.new_password,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(f"Password reset successfully for user: {user.email}")

        return MessageResponse(
            message="Password reset successfully. You can now log in with your new password."
        )

    except (ValueError, HTTPException) as e:
        # Invalid token, expired token, weak password, or HTTPException from auth_service
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during password reset: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset password. Please try again.",
        )
