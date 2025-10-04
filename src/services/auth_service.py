"""Authentication service for user management and authentication flows.

This service orchestrates all authentication-related operations including:
- User registration with email verification
- User login with JWT token generation
- Token refresh flow
- Password reset request and confirmation
- Email verification
- User profile management

Note: This service is asynchronous (uses `async def`) because it performs
database I/O operations and calls other async services.
See docs/development/architecture/async-vs-sync-patterns.md for details.
"""

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from fastapi import HTTPException, status

from src.models.user import User
from src.models.auth import RefreshToken, EmailVerificationToken, PasswordResetToken
from src.services.password_service import PasswordService
from src.services.jwt_service import JWTService
from src.services.email_service import EmailService
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class AuthService:
    """Service for user authentication and management.

    This service orchestrates authentication workflows by coordinating
    between database operations, password hashing, JWT generation, and
    email sending. All methods are asynchronous due to database I/O.

    Workflows:
        - Registration: Create user → Send verification email
        - Verification: Validate token → Activate user → Send welcome email
        - Login: Verify credentials → Generate tokens → Create refresh token
        - Refresh: Validate refresh token → Generate new access token
        - Password Reset: Generate token → Send email → Validate → Update password

    Attributes:
        session: Database session for async operations
        password_service: Service for password operations (sync)
        jwt_service: Service for JWT operations (sync)
        email_service: Service for email operations (async)
    """

    def __init__(self, session: AsyncSession, development_mode: bool = False):
        """Initialize auth service with dependencies.

        Args:
            session: Async database session
            development_mode: If True, emails are logged instead of sent
        """
        self.session = session
        self.password_service = PasswordService()
        self.jwt_service = JWTService()
        self.email_service = EmailService(development_mode=development_mode)
        self.settings = get_settings()

    async def register_user(
        self, email: str, password: str, name: Optional[str] = None
    ) -> User:
        """Register a new user with email verification.

        Creates a new user account with hashed password and sends
        verification email. User account is inactive until verified.

        Args:
            email: User's email address (unique)
            password: Plain text password (will be hashed)
            name: User's full name (optional)

        Returns:
            Created user instance (unverified)

        Raises:
            HTTPException: If email already exists or password is weak

        Example:
            >>> service = AuthService(session)
            >>> user = await service.register_user(
            ...     email="user@example.com",
            ...     password="SecurePass123!",
            ...     name="John Doe"
            ... )
            >>> user.is_verified
            False
        """
        # Check if email already exists
        result = await self.session.execute(select(User).where(User.email == email))
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        # Validate password strength
        is_valid, error_message = self.password_service.validate_password_strength(
            password
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
            )

        # Hash password
        password_hash = self.password_service.hash_password(password)

        # Create user
        user = User(
            email=email,
            password_hash=password_hash,
            name=name,
            is_active=True,  # Account is active but not verified
            is_verified=False,
        )

        self.session.add(user)
        await self.session.flush()  # Get user ID
        await self.session.refresh(user)

        # Generate verification token
        verification_token = await self._create_verification_token(user.id)

        # Send verification email (non-blocking)
        try:
            await self.email_service.send_verification_email(
                to_email=email,
                verification_token=verification_token.token,
                user_name=name,
            )
            logger.info(f"Verification email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send verification email to {email}: {e}")
            # Don't fail registration if email fails - user can request resend

        await self.session.commit()

        logger.info(f"User registered: {email} (ID: {user.id})")
        return user

    async def verify_email(self, token: str) -> User:
        """Verify user's email address using verification token.

        Validates the token, activates the user account, and sends
        a welcome email.

        Args:
            token: Email verification token string

        Returns:
            Verified user instance

        Raises:
            HTTPException: If token is invalid or expired

        Example:
            >>> service = AuthService(session)
            >>> user = await service.verify_email("abc123def456")
            >>> user.is_verified
            True
        """
        # Find verification token
        result = await self.session.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token == token,
                EmailVerificationToken.used_at.is_(None),
            )
        )
        verification_token = result.scalar_one_or_none()

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
        user.is_verified = True
        user.verified_at = datetime.now(timezone.utc)

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

    async def login(self, email: str, password: str) -> Tuple[str, str, User]:
        """Authenticate user and generate JWT tokens.

        Verifies credentials and generates both access and refresh tokens.
        Refresh token is stored in database for revocation capability.

        Args:
            email: User's email address
            password: Plain text password

        Returns:
            Tuple of (access_token, refresh_token, user)

        Raises:
            HTTPException: If credentials invalid or user not verified

        Example:
            >>> service = AuthService(session)
            >>> access, refresh, user = await service.login(
            ...     email="user@example.com",
            ...     password="SecurePass123!"
            ... )
        """
        # Get user by email
        result = await self.session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Verify password
        if not self.password_service.verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled"
            )

        # Check if email is verified
        if not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified. Please check your email for verification link.",
            )

        # Check if password needs rehashing (bcrypt rounds changed)
        if self.password_service.needs_rehash(user.password_hash):
            user.password_hash = self.password_service.hash_password(password)
            logger.info(f"Password rehashed for user {user.email}")

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)

        # Create refresh token in database
        refresh_token_record = await self._create_refresh_token(user.id)

        # Generate JWT tokens
        access_token = self.jwt_service.create_access_token(
            user_id=user.id, email=user.email
        )

        refresh_token = self.jwt_service.create_refresh_token(
            user_id=user.id, jti=refresh_token_record.id
        )

        await self.session.commit()

        logger.info(f"User logged in: {user.email} (ID: {user.id})")
        return access_token, refresh_token, user

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token using refresh token.

        Validates the refresh token and generates a new access token.
        Refresh token remains valid for future use.

        Args:
            refresh_token: JWT refresh token string

        Returns:
            New access token string

        Raises:
            HTTPException: If refresh token invalid or revoked

        Example:
            >>> service = AuthService(session)
            >>> new_access_token = await service.refresh_access_token(refresh_token)
        """
        try:
            # Decode and validate refresh token
            token_jti = self.jwt_service.get_token_jti(refresh_token)
            user_id = self.jwt_service.get_user_id_from_token(refresh_token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid refresh token: {str(e)}",
            )

        # Check if refresh token exists and is valid
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.id == token_jti,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        refresh_token_record = result.scalar_one_or_none()

        if not refresh_token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found or revoked",
            )

        # Check if token expired
        if datetime.now(timezone.utc) > refresh_token_record.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )

        # Get user
        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Generate new access token
        access_token = self.jwt_service.create_access_token(
            user_id=user.id, email=user.email
        )

        logger.info(f"Access token refreshed for user: {user.email} (ID: {user.id})")
        return access_token

    async def logout(self, refresh_token: str) -> None:
        """Logout user by revoking refresh token.

        Marks the refresh token as revoked so it cannot be used again.
        Access tokens remain valid until expiration (stateless).

        Args:
            refresh_token: JWT refresh token string

        Raises:
            HTTPException: If refresh token invalid

        Example:
            >>> service = AuthService(session)
            >>> await service.logout(refresh_token)
        """
        try:
            token_jti = self.jwt_service.get_token_jti(refresh_token)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid refresh token: {str(e)}",
            )

        # Find and revoke refresh token
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.id == token_jti, RefreshToken.revoked_at.is_(None)
            )
        )
        refresh_token_record = result.scalar_one_or_none()

        if refresh_token_record:
            refresh_token_record.revoked_at = datetime.now(timezone.utc)
            await self.session.commit()
            logger.info(f"Refresh token revoked: {token_jti}")
        else:
            logger.warning(f"Refresh token not found or already revoked: {token_jti}")

    async def request_password_reset(self, email: str) -> None:
        """Request password reset by sending reset email.

        Generates a password reset token and sends email with reset link.
        Always succeeds to prevent email enumeration attacks.

        Args:
            email: User's email address

        Example:
            >>> service = AuthService(session)
            >>> await service.request_password_reset("user@example.com")
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

        # Generate reset token
        reset_token = await self._create_password_reset_token(user.id)

        # Send password reset email
        try:
            await self.email_service.send_password_reset_email(
                to_email=email, reset_token=reset_token.token, user_name=user.name
            )
            logger.info(f"Password reset email sent to {email}")
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")

        await self.session.commit()

    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset user password using reset token.

        Validates the reset token, updates password, and sends
        confirmation email.

        Args:
            token: Password reset token string
            new_password: New plain text password

        Returns:
            User instance with updated password

        Raises:
            HTTPException: If token invalid/expired or password weak

        Example:
            >>> service = AuthService(session)
            >>> user = await service.reset_password(
            ...     token="xyz789",
            ...     new_password="NewSecurePass123!"
            ... )
        """
        # Find reset token
        result = await self.session.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token == token, PasswordResetToken.used_at.is_(None)
            )
        )
        reset_token = result.scalar_one_or_none()

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

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID.

        Args:
            user_id: User's unique identifier

        Returns:
            User instance or None if not found

        Example:
            >>> service = AuthService(session)
            >>> user = await service.get_user_by_id(user_id)
        """
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email address.

        Args:
            email: User's email address

        Returns:
            User instance or None if not found

        Example:
            >>> service = AuthService(session)
            >>> user = await service.get_user_by_email("user@example.com")
        """
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_user_profile(
        self, user_id: UUID, name: Optional[str] = None
    ) -> User:
        """Update user profile information.

        Args:
            user_id: User's unique identifier
            name: New name (optional)

        Returns:
            Updated user instance

        Raises:
            HTTPException: If user not found

        Example:
            >>> service = AuthService(session)
            >>> user = await service.update_user_profile(
            ...     user_id=user_id,
            ...     name="Jane Doe"
            ... )
        """
        user = await self.get_user_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        if name is not None:
            user.name = name

        await self.session.commit()
        await self.session.refresh(user)

        logger.info(f"Profile updated for user: {user.email} (ID: {user.id})")
        return user

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> User:
        """Change user password (requires current password).

        Args:
            user_id: User's unique identifier
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            User instance with updated password

        Raises:
            HTTPException: If current password wrong or new password weak

        Example:
            >>> service = AuthService(session)
            >>> user = await service.change_password(
            ...     user_id=user_id,
            ...     current_password="OldPass123!",
            ...     new_password="NewSecurePass123!"
            ... )
        """
        user = await self.get_user_by_id(user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Verify current password
        if not self.password_service.verify_password(
            current_password, user.password_hash
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
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

        await self.session.commit()

        # Send notification email
        try:
            await self.email_service.send_password_changed_notification(
                to_email=user.email, user_name=user.name
            )
            logger.info(f"Password changed notification sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send password changed email to {user.email}: {e}")

        logger.info(f"Password changed for user: {user.email} (ID: {user.id})")
        return user

    # Private helper methods

    async def _create_verification_token(self, user_id: UUID) -> EmailVerificationToken:
        """Create email verification token for user.

        Args:
            user_id: User's unique identifier

        Returns:
            Created verification token instance
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
        )

        verification_token = EmailVerificationToken(
            user_id=user_id, token=token, expires_at=expires_at
        )

        self.session.add(verification_token)
        await self.session.flush()

        return verification_token

    async def _create_refresh_token(self, user_id: UUID) -> RefreshToken:
        """Create refresh token for user.

        Args:
            user_id: User's unique identifier

        Returns:
            Created refresh token instance
        """
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        refresh_token = RefreshToken(user_id=user_id, expires_at=expires_at)

        self.session.add(refresh_token)
        await self.session.flush()
        await self.session.refresh(refresh_token)

        return refresh_token

    async def _create_password_reset_token(self, user_id: UUID) -> PasswordResetToken:
        """Create password reset token for user.

        Args:
            user_id: User's unique identifier

        Returns:
            Created reset token instance
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(
            hours=self.settings.PASSWORD_RESET_TOKEN_EXPIRE_HOURS
        )

        reset_token = PasswordResetToken(
            user_id=user_id, token=token, expires_at=expires_at
        )

        self.session.add(reset_token)
        await self.session.flush()

        return reset_token
