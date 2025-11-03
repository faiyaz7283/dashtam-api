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

import hashlib
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
from src.models.session import Session
from src.services.password_service import PasswordService
from src.services.jwt_service import JWTService
from src.services.verification_service import VerificationService
from src.services.password_reset_service import PasswordResetService
from src.services.token_rotation_service import TokenRotationService
from src.services.email_service import EmailService
from src.services.geolocation_service import get_geolocation_service
from src.core.config import get_settings
from src.core.cache import CacheBackend, CacheError, get_cache
from redis.exceptions import RedisError

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

    def __init__(self, session: AsyncSession, cache: Optional[CacheBackend] = None):
        """Initialize auth service with dependencies.

        Args:
            session: Async database session
            cache: Cache backend for token blacklist (SOLID: Dependency Injection)

        Note:
            Development mode is automatically determined from settings.DEBUG.
            When DEBUG=True, emails are logged instead of sent.
            Cache is optional (defaults to singleton if not provided).
        """
        self.session = session
        self.settings = get_settings()
        self.password_service = PasswordService()
        self.jwt_service = JWTService()
        # Delegate to specialized services for verification and password reset
        self.verification_service = VerificationService(session)
        self.password_reset_service = PasswordResetService(session)
        # Email service for notifications
        self.email_service = EmailService(development_mode=self.settings.DEBUG)
        # Session management: geolocation for IP → location
        self.geolocation_service = get_geolocation_service()
        # Cache for token blacklist (immediate revocation)
        self.cache = cache or get_cache()

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

    async def login(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, str, User]:
        """Authenticate user and generate JWT tokens with session tracking.

        Verifies credentials and generates both access and refresh tokens.
        Refresh token is stored in database with session metadata (location,
        device info, fingerprint) for session management.

        Args:
            email: User's email address
            password: Plain text password
            ip_address: Client IP address (for geolocation)
            user_agent: Client User-Agent header (for device fingerprinting)

        Returns:
            Tuple of (access_token, refresh_token, user)

        Raises:
            HTTPException: If credentials invalid or user not verified

        Example:
            >>> service = AuthService(session)
            >>> access, refresh, user = await service.login(
            ...     email="user@example.com",
            ...     password="SecurePass123!",
            ...     ip_address="203.0.113.1",
            ...     user_agent="Mozilla/5.0 ..."
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

        # 1. Create session with device/browser metadata
        session_record = await self._create_session(
            user_id=user.id, ip_address=ip_address, user_agent=user_agent
        )

        # 2. Create opaque refresh token linked to session (Pattern A)
        refresh_token, refresh_token_record = await self._create_refresh_token(
            user_id=user.id, session_id=session_record.id
        )

        # Generate JWT access token (stateless) with session link (jti claim) and version
        access_token = self.jwt_service.create_access_token(
            user_id=user.id,
            email=user.email,
            refresh_token_id=refresh_token_record.id,
            token_version=user.min_token_version,
        )

        await self.session.commit()

        logger.info(f"User logged in: {user.email} (ID: {user.id})")
        return access_token, refresh_token, user

    async def refresh_access_token(
        self,
        refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Generate new access token using opaque refresh token with session tracking.

        Validates the opaque refresh token by hashing and database lookup.
        Updates last_used_at on the refresh token for session tracking.
        Generates JWT with jti claim linking to refresh token (session ID).
        This is Pattern A (industry standard): JWT access + opaque refresh.

        Args:
            refresh_token: Opaque refresh token string (not JWT)
            ip_address: Client IP address (for activity tracking)
            user_agent: Client User-Agent header (for fingerprint validation)

        Returns:
            New JWT access token string

        Raises:
            HTTPException: If refresh token invalid, expired, or revoked

        Example:
            >>> service = AuthService(session)
            >>> new_access_token = await service.refresh_access_token(
            ...     refresh_token=refresh_token,
            ...     ip_address="203.0.113.1",
            ...     user_agent="Mozilla/5.0 ..."
            ... )
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

        # Check if token is blacklisted in cache (immediate revocation)
        # This provides instant revocation even if DB hasn't propagated yet
        blacklist_key = f"revoked_token:{refresh_token_record.id}"
        try:
            is_blacklisted = await self.cache.exists(blacklist_key)
            if is_blacklisted:
                logger.warning(
                    f"Blacklisted token used: {refresh_token_record.id} "
                    f"(user: {refresh_token_record.user_id})"
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token has been revoked",
                )
        except (CacheError, RedisError) as e:
            # Log cache error but don't fail (DB check below is fallback)
            # Note: Don't catch HTTPException - let it propagate (security)
            logger.error(f"Cache blacklist check failed: {e}")

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

        # Validate token versions (hybrid rotation check)
        is_valid, failure_reason = await self._validate_token_versions(
            refresh_token_record, user
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token has been rotated: {failure_reason}",
            )

        # Update session last_activity (session tracking)
        if refresh_token_record.session_id:
            result = await self.session.execute(
                select(Session).where(Session.id == refresh_token_record.session_id)
            )
            session_record = result.scalar_one_or_none()
            if session_record:
                session_record.last_activity = datetime.now(timezone.utc)

        # Generate new JWT access token with jti claim (links to session) and version
        access_token = self.jwt_service.create_access_token(
            user_id=user.id,
            email=user.email,
            refresh_token_id=refresh_token_record.id,
            token_version=user.min_token_version,
        )

        await self.session.commit()

        logger.info(
            f"Access token refreshed for user: {user.email} (ID: {user.id}), "
            f"session: {refresh_token_record.id}"
        )
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

    async def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> User:
        """Reset user password using reset token.

        Delegates to PasswordResetService for token validation, password update,
        session revocation, and confirmation email.

        Security: All active refresh tokens are revoked to ensure that any
        potentially compromised sessions are terminated. This forces users
        to log in again with the new password on all devices.

        Args:
            token: Password reset token string
            new_password: New plain text password
            ip_address: Client IP address for audit trail
            user_agent: Client User-Agent for audit trail

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
        return await self.password_reset_service.reset_password(
            token, new_password, ip_address=ip_address, user_agent=user_agent
        )

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
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> User:
        """Change user password (requires current password).

        Args:
            user_id: User's unique identifier
            current_password: Current password for verification
            new_password: New password to set
            ip_address: Client IP address for audit trail
            user_agent: Client User-Agent for audit trail

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

        # Validate new password is not the same as current
        if self.password_service.verify_password(new_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password cannot be the same as current password",
            )

        # Validate new password strength
        is_valid, error_message = self.password_service.validate_password_strength(
            new_password
        )
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error_message
            )

        # Update password
        user.password_hash = self.password_service.hash_password(new_password)

        # 🔒 SECURITY: Rotate all tokens (logout all other devices)
        # Uses TokenRotationService to increment min_token_version and invalidate all existing tokens
        # This prevents compromised sessions from remaining active after password change
        rotation_service = TokenRotationService(self.session)
        rotation_result = await rotation_service.rotate_user_tokens(
            user_id=user.id,
            reason="Password changed by user",
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Commit password change and token rotation together (atomic)
        await self.session.commit()

        logger.info(
            f"Password changed for user {user.email}: Rotated tokens (version {rotation_result.old_version} → {rotation_result.new_version}, revoked {rotation_result.tokens_revoked} tokens)"
        )

        # Send notification email
        try:
            await self.email_service.send_password_changed_notification(
                to_email=user.email, user_name=user.name
            )
            logger.info(f"Password changed notification sent to {user.email}")
        except Exception as e:
            logger.error(f"Failed to send password changed email to {user.email}: {e}")

        return user

    # Private helper methods

    async def _create_session(
        self,
        user_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Session:
        """Create a new session with device/browser metadata.

        Args:
            user_id: User's unique identifier
            ip_address: Client IP address (for geolocation)
            user_agent: Client User-Agent header (for fingerprinting)

        Returns:
            Created Session record
        """
        # Session metadata: Get geolocation from IP address
        location = "Unknown Location"
        if ip_address:
            location = self.geolocation_service.get_location(ip_address)

        # Session metadata: Generate device fingerprint from user agent
        fingerprint_string = user_agent or ""
        fingerprint = hashlib.sha256(fingerprint_string.encode("utf-8")).hexdigest()

        # Calculate session expiration
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        # Create Session record
        session_record = Session(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            location=location,
            fingerprint=fingerprint,
            is_trusted_device=False,
            last_activity=datetime.now(timezone.utc),
            expires_at=expires_at,
        )
        self.session.add(session_record)
        await self.session.flush()
        await self.session.refresh(session_record)

        logger.debug(
            f"Session created for user {user_id}: "
            f"session_id={session_record.id}, location={location}"
        )

        return session_record

    async def _create_refresh_token(
        self,
        user_id: UUID,
        session_id: UUID,
    ) -> tuple[str, RefreshToken]:
        """Create opaque refresh token linked to existing session.

        Args:
            user_id: User's unique identifier
            session_id: Session to link this token to

        Returns:
            Tuple of (plain_token, token_record)
            - plain_token: Opaque random token to return to client
            - token_record: Database record with hashed token
        """
        # Generate random opaque token
        plain_token = secrets.token_urlsafe(32)

        # Hash token for storage
        token_hash = self.password_service.hash_password(plain_token)

        # Calculate expiration
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        # Get token versioning info
        from src.models.security_config import SecurityConfig

        result = await self.session.execute(select(SecurityConfig))
        global_config = result.scalar_one()

        result = await self.session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one()

        # Create RefreshToken linked to session
        refresh_token = RefreshToken(
            user_id=user_id,
            session_id=session_id,
            token_hash=token_hash,
            expires_at=expires_at,
            token_version=user.min_token_version,
            global_version_at_issuance=global_config.global_min_token_version,
        )

        self.session.add(refresh_token)
        await self.session.flush()
        await self.session.refresh(refresh_token)

        logger.debug(f"Refresh token created for session {session_id}")

        return plain_token, refresh_token

    async def _validate_token_versions(
        self, token: RefreshToken, user: User
    ) -> tuple[bool, Optional[str]]:
        """Validate token against both global and per-user versions.

        Two-level validation:
        1. Global version check (for system-wide breaches)
        2. Per-user version check (for user-specific events)

        Both checks must pass for token to be valid.

        Args:
            token: RefreshToken to validate.
            user: User who owns the token.

        Returns:
            Tuple of (is_valid, failure_reason).

        Example:
            >>> is_valid, reason = await service._validate_token_versions(token, user)
            >>> if not is_valid:
            ...     raise HTTPException(status_code=401, detail=reason)
        """
        # Get current global version
        from src.models.security_config import SecurityConfig

        result = await self.session.execute(select(SecurityConfig))
        config = result.scalar_one()

        # Check global version (rare, extreme breach)
        if token.global_version_at_issuance < config.global_min_token_version:
            logger.warning(
                f"Token failed global version check: "
                f"token_global_v{token.global_version_at_issuance} < "
                f"required_v{config.global_min_token_version}, "
                f"token_id={token.id}"
            )
            return False, "GLOBAL_TOKEN_VERSION_TOO_OLD"

        # Check per-user version (common, targeted rotation)
        if token.token_version < user.min_token_version:
            logger.info(
                f"Token failed user version check: "
                f"token_v{token.token_version} < "
                f"min_v{user.min_token_version}, "
                f"user_id={user.id}"
            )
            return False, "USER_TOKEN_VERSION_TOO_OLD"

        return True, None
