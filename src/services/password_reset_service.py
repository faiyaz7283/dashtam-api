"""Password reset service.

This service handles all password reset-related operations including:
- Creating password reset tokens
- Validating and consuming reset tokens
- Updating passwords securely
- Revoking active sessions after password change

Extracted from AuthService to follow Single Responsibility Principle.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException, status

from src.models.user import User
from src.models.auth import PasswordResetToken, RefreshToken
from src.services.password_service import PasswordService
from src.services.email_service import EmailService
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class PasswordResetService:
    """Service for password reset workflows.

    This service manages the complete password reset lifecycle:
    - Token generation and email delivery
    - Token validation and expiration checking
    - Password updates with security validation
    - Session revocation after password change

    All tokens are hashed before storage following security best practices.
    """

    def __init__(self, session: AsyncSession):
        """Initialize password reset service.

        Args:
            session: Async database session for operations.
        """
        self.session = session
        self.settings = get_settings()
        self.password_service = PasswordService()
        self.email_service = EmailService(development_mode=self.settings.DEBUG)

    async def request_reset(self, email: str) -> None:
        """Request password reset by sending reset email.

        Generates a password reset token and sends email with reset link.
        Always succeeds to prevent email enumeration attacks (doesn't reveal
        if email exists in system).

        Args:
            email: User's email address.

        Example:
            >>> service = PasswordResetService(session)
            >>> await service.request_reset("user@example.com")
        """
        # Get user by email
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            # Don't reveal that email doesn't exist (prevent enumeration)
            logger.info(f"Password reset requested for non-existent email: {email}")
            return

        if not user.is_active:
            logger.info(f"Password reset requested for inactive user: {email}")
            return

        # Generate reset token (returns plain token and hashed record)
        plain_token = await self._create_password_reset_token(user.id)

        # Send password reset email with plain token
        try:
            await self.email_service.send_password_reset_email(
                to_email=email, reset_token=plain_token, user_name=user.name
            )
            logger.info(f"Password reset email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")

        await self.session.commit()

    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset user password using reset token.

        Validates the reset token, updates password, revokes all existing
        sessions (for security), and sends confirmation email.

        Security: All active refresh tokens are revoked to ensure that any
        potentially compromised sessions are terminated. This forces users
        to log in again with the new password on all devices.

        Args:
            token: Password reset token string.
            new_password: New plain text password.

        Returns:
            User instance with updated password.

        Raises:
            HTTPException: If token invalid/expired or password weak.

        Example:
            >>> service = PasswordResetService(session)
            >>> user = await service.reset_password(
            ...     token="xyz789",
            ...     new_password="NewSecurePass123!"
            ... )
        """
        # Get all unused reset tokens for potential match
        result = await self.session.execute(
            select(PasswordResetToken).where(PasswordResetToken.used_at.is_(None))
        )
        reset_tokens = result.scalars().all()

        # Find matching token by comparing hashes
        reset_token = None
        for token_record in reset_tokens:
            if self.password_service.verify_password(token, token_record.token_hash):
                reset_token = token_record
                break

        if not reset_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used reset token",
            )

        # Check if token expired
        if datetime.now(timezone.utc) > reset_token.expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired",
            )

        # Get user
        result = await self.session.execute(
            select(User).where(User.id == reset_token.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Validate new password
        is_valid, error_message = self.password_service.validate_password_strength(
            new_password
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
            )

        # Update password
        user.password_hash = self.password_service.hash_password(new_password)

        # Mark token as used
        reset_token.used_at = datetime.now(timezone.utc)

        # 🔒 SECURITY: Revoke all existing refresh tokens (logout all devices)
        # This prevents compromised sessions from remaining active after password change
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user.id, ~RefreshToken.is_revoked
            )
        )
        active_tokens = result.scalars().all()

        revoked_count = 0
        for token_record in active_tokens:
            token_record.revoked_at = datetime.now(timezone.utc)
            token_record.is_revoked = True
            revoked_count += 1

        logger.info(
            f"Password reset for user {user.email}: Revoked {revoked_count} active session(s)"
        )

        await self.session.commit()

        # Send confirmation email
        try:
            await self.email_service.send_password_changed_notification(
                to_email=user.email, user_name=user.name
            )
            logger.info(f"Password changed notification sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send password changed email to {user.email}: {e}")

        logger.info(f"Password reset for user: {user.email} (ID: {user.id})")
        return user

    async def _create_password_reset_token(self, user_id: UUID) -> str:
        """Create password reset token for user (private helper).

        Args:
            user_id: User's unique identifier.

        Returns:
            Plain text token to send in email.
        """
        # Generate plain token
        plain_token = secrets.token_urlsafe(32)

        # Hash token for storage (security best practice)
        token_hash = self.password_service.hash_password(plain_token)

        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
        )

        reset_token = PasswordResetToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )

        self.session.add(reset_token)
        await self.session.flush()

        return plain_token
