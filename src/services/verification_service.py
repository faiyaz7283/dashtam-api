"""Email verification service.

This service handles all email verification-related operations including:
- Creating verification tokens
- Validating and consuming verification tokens
- Sending verification emails

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
from src.models.auth import EmailVerificationToken
from src.services.password_service import PasswordService
from src.services.email_service import EmailService
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class VerificationService:
    """Service for email verification workflows.

    This service manages the complete email verification lifecycle:
    - Token generation and storage
    - Token validation and expiration checking
    - Email delivery
    - User account activation

    All tokens are hashed before storage following security best practices.
    """

    def __init__(self, session: AsyncSession):
        """Initialize verification service.

        Args:
            session: Async database session for operations.
        """
        self.session = session
        self.settings = get_settings()
        self.password_service = PasswordService()
        self.email_service = EmailService(development_mode=self.settings.DEBUG)

    async def create_verification_token(
        self, user_id: UUID, email: str, user_name: str = None
    ) -> str:
        """Create verification token and send verification email.

        Generates a secure random token, hashes it for storage, and sends
        verification email to the user.

        Args:
            user_id: User's unique identifier.
            email: User's email address.
            user_name: User's name for email personalization.

        Returns:
            Plain text token (for testing/logging only - never expose to user).

        Example:
            >>> service = VerificationService(session)
            >>> token = await service.create_verification_token(
            ...     user_id=user.id,
            ...     email="user@example.com",
            ...     user_name="John Doe"
            ... )
        """
        # Generate plain token
        plain_token = secrets.token_urlsafe(32)

        # Hash token for storage (security best practice)
        token_hash = self.password_service.hash_password(plain_token)

        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        )

        verification_token = EmailVerificationToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )

        self.session.add(verification_token)
        await self.session.flush()

        # Send verification email with plain token
        try:
            await self.email_service.send_verification_email(
                to_email=email, verification_token=plain_token, user_name=user_name
            )
            logger.info(f"Verification email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")
            # Don't fail - user can request resend

        return plain_token

    async def verify_email(self, token: str) -> User:
        """Verify user's email address using verification token.

        Validates the token, checks expiration, marks user as verified,
        and sends welcome email.

        Args:
            token: Email verification token string.

        Returns:
            Verified user instance.

        Raises:
            HTTPException: If token is invalid, expired, or already used.

        Example:
            >>> service = VerificationService(session)
            >>> user = await service.verify_email("abc123def456")
            >>> user.email_verified
            True
        """
        # Get all unused verification tokens for potential match
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.used_at.is_(None),
            )
        )
        verification_tokens = result.scalars().all()

        # Find matching token by comparing hashes
        verification_token = None
        for token_record in verification_tokens:
            if self.password_service.verify_password(token, token_record.token_hash):
                verification_token = token_record
                break

        if not verification_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already used verification token",
            )

        # Check if token expired
        if datetime.now(timezone.utc) > verification_token.expires_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired",
            )

        # Get user
        result = await self.session.execute(
            select(User).where(User.id == verification_token.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Mark user as verified
        user.email_verified = True
        user.email_verified_at = datetime.now(timezone.utc)

        # Mark token as used
        verification_token.used_at = datetime.now(timezone.utc)

        await self.session.commit()

        # Send welcome email
        try:
            await self.email_service.send_welcome_email(
                to_email=user.email, user_name=user.name
            )
            logger.info(f"Welcome email sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user.email}: {e}")

        logger.info(f"Email verified for user: {user.email} (ID: {user.id})")
        return user
