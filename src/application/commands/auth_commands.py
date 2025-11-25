"""Authentication commands (CQRS write operations).

Commands represent user intent to change system state.
All commands are immutable (frozen=True) and use keyword-only arguments (kw_only=True).

Pattern:
- Commands are data containers (no logic)
- Handlers execute business logic
- Commands don't return values (handlers return Result types)
- Use Annotated types for validation (DRY principle)
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.types import Email, Password, RefreshToken, VerificationToken


@dataclass(frozen=True, kw_only=True)
class RegisterUser:
    """Register new user account.

    Creates user with email/password, generates email verification token.
    User cannot login until email is verified.

    Attributes:
        email: User's email address (validated, normalized).
        password: User's password (validated strength, plain text, will be hashed).

    Example:
        >>> command = RegisterUser(
        ...     email="user@example.com",
        ...     password="SecurePass123!",
        ... )
        >>> result = await handler.handle(command)
    """

    email: Email
    password: Password


@dataclass(frozen=True, kw_only=True)
class LoginUser:
    """Authenticate user and create session.

    Validates credentials, checks email verification, checks account lockout.
    Returns JWT access token + refresh token on success.

    Attributes:
        email: User's email address (validated, normalized).
        password: User's password (plain text, validated strength).
        ip_address: Client IP address (for audit, session tracking).
        user_agent: Client user agent (for audit, session tracking).

    Example:
        >>> command = LoginUser(
        ...     email="user@example.com",
        ...     password="SecurePass123!",
        ...     ip_address="192.168.1.1",
        ...     user_agent="Mozilla/5.0...",
        ... )
        >>> result = await handler.handle(command)
    """

    email: Email
    password: Password
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, kw_only=True)
class VerifyEmail:
    """Verify user's email address.

    Validates verification token, marks user as verified.
    User can login after email verification.

    Attributes:
        token: Email verification token (validated hex format).

    Example:
        >>> command = VerifyEmail(token="abc123def456...")
        >>> result = await handler.handle(command)
    """

    token: VerificationToken


@dataclass(frozen=True, kw_only=True)
class RefreshAccessToken:
    """Refresh access token using refresh token.

    Validates refresh token, generates new access token + new refresh token.
    Implements token rotation (old refresh token deleted).

    Attributes:
        refresh_token: Opaque refresh token (validated urlsafe base64 format).

    Example:
        >>> command = RefreshAccessToken(refresh_token="dGhpcyBpcyB...")
        >>> result = await handler.handle(command)
    """

    refresh_token: RefreshToken


@dataclass(frozen=True, kw_only=True)
class RequestPasswordReset:
    """Request password reset for user.

    Generates password reset token, sends email with reset link.
    Always returns success (no user enumeration).

    Attributes:
        email: User's email address (validated, normalized).
        ip_address: Client IP address (for audit, abuse detection).
        user_agent: Client user agent (for audit).

    Example:
        >>> command = RequestPasswordReset(
        ...     email="user@example.com",
        ...     ip_address="192.168.1.1",
        ...     user_agent="Mozilla/5.0...",
        ... )
        >>> result = await handler.handle(command)
    """

    email: Email
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, kw_only=True)
class ConfirmPasswordReset:
    """Confirm password reset with token and new password.

    Validates reset token, updates user password, revokes all sessions.
    Forces user to login again after password change.

    Attributes:
        token: Password reset token (validated hex format).
        new_password: New password (validated strength, plain text, will be hashed).

    Example:
        >>> command = ConfirmPasswordReset(
        ...     token="xyz789abc123...",
        ...     new_password="NewSecurePass456!",
        ... )
        >>> result = await handler.handle(command)
    """

    token: VerificationToken
    new_password: Password


@dataclass(frozen=True, kw_only=True)
class LogoutUser:
    """Logout user and revoke refresh token.

    Revokes refresh token associated with current session.
    JWT access token cannot be revoked (expires naturally in 15 minutes).

    Attributes:
        user_id: User's unique identifier (from JWT).
        refresh_token: Refresh token to revoke (validated urlsafe base64 format).

    Example:
        >>> command = LogoutUser(
        ...     user_id=UUID("123e4567-e89b-12d3-a456-426614174000"),
        ...     refresh_token="dGhpcyBpcyB...",
        ... )
        >>> result = await handler.handle(command)
    """

    user_id: UUID
    refresh_token: RefreshToken  # Type alias from domain.types
