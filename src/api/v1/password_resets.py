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
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_session
from src.schemas.common import MessageResponse
from src.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Schemas


class CreatePasswordResetRequest(BaseModel):
    """Request to create a password reset.

    Attributes:
        email: Email address to send reset link to.
    """

    email: EmailStr = Field(
        ..., description="Email address to send password reset link"
    )

    model_config = {"json_schema_extra": {"example": {"email": "john.doe@example.com"}}}


class VerifyResetTokenResponse(BaseModel):
    """Response for token verification.

    Attributes:
        valid: Whether the token is valid.
        email: Email address associated with token (only if valid).
        expires_at: Token expiration timestamp (only if valid).
    """

    valid: bool = Field(..., description="Whether the token is valid")
    email: Optional[str] = Field(
        default=None, description="Email address associated with token"
    )
    expires_at: Optional[str] = Field(
        default=None, description="Token expiration timestamp (ISO 8601)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "valid": True,
                "email": "john.doe@example.com",
                "expires_at": "2025-10-05T12:00:00Z",
            }
        }
    }


class CompletePasswordResetRequest(BaseModel):
    """Request to complete password reset.

    Attributes:
        new_password: New password meeting strength requirements.
    """

    new_password: str = Field(
        ...,
        description="New password (min 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special)",
        min_length=8,
        max_length=128,
    )

    model_config = {"json_schema_extra": {"example": {"new_password": "NewSecure123!"}}}


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
        # Verify the token and get associated email
        # This is a new method we'll need to add to AuthService
        from src.models.auth import PasswordResetToken
        from sqlmodel import select

        result = await session.execute(
            select(PasswordResetToken).where(PasswordResetToken.token == token)
        )
        reset_token = result.scalar_one_or_none()

        if not reset_token or not reset_token.is_valid:
            return VerifyResetTokenResponse(valid=False)

        # Get user email
        from src.models.user import User

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
) -> MessageResponse:
    """Complete password reset with new password.

    Validates the token and updates the user's password.

    Args:
        token: Password reset token from email.
        request: New password.
        session: Database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if token invalid or expired, or password weak.
    """
    auth_service = AuthService(session)

    try:
        # Reset password (confirmation email sent internally by AuthService)
        user = await auth_service.reset_password(
            token=token, new_password=request.new_password
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
