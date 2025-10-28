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
from src.models.auth import RefreshToken
from src.services.password_service import PasswordService
from src.services.jwt_service import JWTService
from src.services.verification_service import VerificationService
from src.services.password_reset_service import PasswordResetService
from src.core.config import get_settings

logger = logging.getLogger(__name__)


class AuthService:
    """Service for user authentication and management (orchestrator).

    This service orchestrates authentication workflows by delegating to
    specialized services while maintaining a unified public API.

    Workflows:
        - Registration: Create user → Delegate verification to VerificationService
        - Verification: Delegate to VerificationService
        - Login: Verify credentials → Generate tokens → Create refresh token
        - Refresh: Validate refresh token → Generate new access token
        - Password Reset: Delegate to PasswordResetService

    Attributes:
        session: Database session for async operations
        password_service: Service for password operations (sync)
        jwt_service: Service for JWT operations (sync)
        verification_service: Service for email verification workflows
        password_reset_service: Service for password reset workflows
    """

    def __init__(self, session: AsyncSession):
        """Initialize auth service with dependencies.

        Args:
            session: Async database session

        Note:
            Development mode is automatically determined from settings.DEBUG.
            When DEBUG=True, emails are logged instead of sent.
        """
        self.session = session
        self.settings = get_settings()
        self.password_service = PasswordService()
        self.jwt_service = JWTService()
        # Delegate to specialized services for verification and password reset
        self.verification_service = VerificationService(session)
        self.password_reset_service = PasswordResetService(session)

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
            email_verified=False,
        )

        self.session.add(user)
        await self.session.flush()  # Get user ID
        await self.session.refresh(user)

        # Delegate to VerificationService to create token and send email
        await self.verification_service.create_verification_token(
            user_id=user.id, email=email, user_name=name
        )

        await self.session.commit()

        logger.info(f"User registered: {email} (ID: {user.id})")
        return user

    async def verify_email(self, token: str) -> User:
        """Verify user's email address using verification token.

        Delegates to VerificationService for token validation and user activation.

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
        # Delegate to VerificationService
        return await self.verification_service.verify_email(token)

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
        if not user.email_verified:
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

        # Generate JWT access token (stateless)
        access_token = self.jwt_service.create_access_token(
            user_id=user.id, email=user.email
        )

        # Generate opaque refresh token (stateful, hashed in DB)
        # Pattern A: Opaque tokens, not JWT (industry standard)
        refresh_token, refresh_token_record = await self._create_refresh_token(user.id)

        await self.session.commit()

        logger.info(f"User logged in: {user.email} (ID: {user.id})")
        return access_token, refresh_token, user

    async def refresh_access_token(self, refresh_token: str) -> str:
        """Generate new access token using opaque refresh token.

        Validates the opaque refresh token by hashing and database lookup.
        This is Pattern A (industry standard): JWT access + opaque refresh.

        Args:
            refresh_token: Opaque refresh token string (not JWT)

        Returns:
            New JWT access token string

        Raises:
            HTTPException: If refresh token invalid, expired, or revoked

        Example:
            >>> service = AuthService(session)
            >>> new_access_token = await service.refresh_access_token(refresh_token)
        """
        # Get all active (non-revoked) refresh tokens
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        )
        refresh_tokens = result.scalars().all()

        # Find matching token by comparing hashes (secure validation)
        refresh_token_record = None
        for token_record in refresh_tokens:
            if self.password_service.verify_password(
                refresh_token, token_record.token_hash
            ):
                refresh_token_record = token_record
                break

        if not refresh_token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or revoked refresh token",
            )

        # Check if token expired
        if datetime.now(timezone.utc) > refresh_token_record.expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )

        # Get user
        result = await self.session.execute(
            select(User).where(User.id == refresh_token_record.user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
            )

        # Generate new JWT access token
        access_token = self.jwt_service.create_access_token(
            user_id=user.id, email=user.email
        )

        logger.info(f"Access token refreshed for user: {user.email} (ID: {user.id})")
        return access_token

    async def logout(self, refresh_token: str) -> None:
        """Logout user by revoking opaque refresh token.

        Validates the opaque refresh token by hashing and database lookup,
        then marks it as revoked. Access tokens remain valid until expiration.
        This is Pattern A (industry standard): JWT access + opaque refresh.

        Args:
            refresh_token: Opaque refresh token string (not JWT)

        Raises:
            HTTPException: If refresh token invalid

        Example:
            >>> service = AuthService(session)
            >>> await service.logout(refresh_token)
        """
        # Get all active (non-revoked) refresh tokens
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.revoked_at.is_(None))
        )
        refresh_tokens = result.scalars().all()

        # Find matching token by comparing hashes (secure validation)
        refresh_token_record = None
        for token_record in refresh_tokens:
            if self.password_service.verify_password(
                refresh_token, token_record.token_hash
            ):
                refresh_token_record = token_record
                break

        if refresh_token_record:
            # Revoke the token
            refresh_token_record.revoked_at = datetime.now(timezone.utc)
            refresh_token_record.is_revoked = True
            await self.session.commit()
            logger.info(
                f"Refresh token revoked for user: {refresh_token_record.user_id}"
            )
        else:
            # Don't reveal if token doesn't exist (security best practice)
            logger.warning("Logout attempted with invalid or already revoked token")

    async def request_password_reset(self, email: str) -> None:
        """Request password reset by sending reset email.

        Delegates to PasswordResetService for token generation and email.
        Always succeeds to prevent email enumeration attacks.

        Args:
            email: User's email address

        Example:
            >>> service = AuthService(session)
            >>> await service.request_password_reset("user@example.com")
        """
        # Delegate to PasswordResetService
        await self.password_reset_service.request_reset(email)

    async def reset_password(self, token: str, new_password: str) -> User:
        """Reset user password using reset token.

        Delegates to PasswordResetService for token validation, password update,
        session revocation, and confirmation email.

        Security: All active refresh tokens are revoked to ensure that any
        potentially compromised sessions are terminated. This forces users
        to log in again with the new password on all devices.

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
        # Delegate to PasswordResetService
        return await self.password_reset_service.reset_password(token, new_password)

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

    async def _create_refresh_token(self, user_id: UUID) -> tuple[str, RefreshToken]:
        """Create opaque refresh token for user (Industry Standard Pattern A).

        Generates a random opaque token (not JWT), hashes it for storage,
        and returns both the plain token and the database record.
        This is the industry standard pattern used by Auth0, GitHub, etc.

        Args:
            user_id: User's unique identifier

        Returns:
            Tuple of (plain_token, token_record)
            - plain_token: Opaque random token to return to client
            - token_record: Database record with hashed token
        """
        # Generate random opaque token (like email verification)
        plain_token = secrets.token_urlsafe(32)

        # Hash token for storage (security best practice)
        token_hash = self.password_service.hash_password(plain_token)

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        # Create refresh token record with hash
        refresh_token = RefreshToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at
        )

        self.session.add(refresh_token)
        await self.session.flush()
        await self.session.refresh(refresh_token)

        return plain_token, refresh_token
