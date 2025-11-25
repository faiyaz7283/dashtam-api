"""Authentication domain events (Phase 1 - MVP).

Pattern: 3 events per workflow (ATTEMPTED → SUCCEEDED/FAILED)
- *Attempted: User initiated action (before business logic)
- *Succeeded: Operation completed successfully (after business commit)
- *Failed: Operation failed (after business rollback)

Handlers:
- LoggingEventHandler: ALL 3 events
- AuditEventHandler: ALL 3 events
- EmailEventHandler: SUCCEEDED only
- SessionEventHandler: SUCCEEDED only
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent


# ═══════════════════════════════════════════════════════════════
# User Registration (Workflow 1)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class UserRegistrationAttempted(DomainEvent):
    """User registration attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record USER_REGISTRATION_ATTEMPTED

    Attributes:
        email: Email address attempted.
    """

    email: str


@dataclass(frozen=True, kw_only=True)
class UserRegistrationSucceeded(DomainEvent):
    """User registration completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record USER_REGISTERED
    - EmailEventHandler: Send verification email

    Attributes:
        user_id: ID of newly registered user.
        email: User's email address.
        verification_token: Email verification token (for email handler).
    """

    user_id: UUID
    email: str
    verification_token: str


@dataclass(frozen=True, kw_only=True)
class UserRegistrationFailed(DomainEvent):
    """User registration failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record USER_REGISTRATION_FAILED

    Attributes:
        email: Email address attempted.
        reason: Failure reason (e.g., "duplicate_email", "invalid_email").
    """

    email: str
    reason: str


# ═══════════════════════════════════════════════════════════════
# User Login (Workflow 2)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class UserLoginAttempted(DomainEvent):
    """User login attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record USER_LOGIN_ATTEMPTED

    Attributes:
        email: Email address attempted.
    """

    email: str


@dataclass(frozen=True, kw_only=True)
class UserLoginSucceeded(DomainEvent):
    """User login completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record USER_LOGIN_SUCCESS

    Attributes:
        user_id: ID of logged in user.
        email: User's email address.
        session_id: Created session ID (for tracking).
    """

    user_id: UUID
    email: str
    session_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class UserLoginFailed(DomainEvent):
    """User login failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record USER_LOGIN_FAILED

    Attributes:
        email: Email address attempted.
        reason: Failure reason (e.g., "invalid_credentials", "email_not_verified",
            "account_locked").
        user_id: User ID if found (for tracking lockout).
    """

    email: str
    reason: str
    user_id: UUID | None = None


# ═══════════════════════════════════════════════════════════════
# Email Verification (Workflow 3)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class EmailVerificationAttempted(DomainEvent):
    """Email verification attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record EMAIL_VERIFICATION_ATTEMPTED

    Attributes:
        token: Verification token attempted (truncated for security).
    """

    token: str  # First 8 chars only for logging


@dataclass(frozen=True, kw_only=True)
class EmailVerificationSucceeded(DomainEvent):
    """Email verification completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record EMAIL_VERIFIED

    Attributes:
        user_id: ID of verified user.
        email: User's email address.
    """

    user_id: UUID
    email: str


@dataclass(frozen=True, kw_only=True)
class EmailVerificationFailed(DomainEvent):
    """Email verification failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record EMAIL_VERIFICATION_FAILED

    Attributes:
        token: Verification token attempted (truncated for security).
        reason: Failure reason (e.g., "token_not_found", "token_expired",
            "token_already_used").
    """

    token: str  # First 8 chars only for logging
    reason: str


# ═══════════════════════════════════════════════════════════════
# Password Change (Workflow 4)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class UserPasswordChangeAttempted(DomainEvent):
    """User password change attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record USER_PASSWORD_CHANGE_ATTEMPTED

    Attributes:
        user_id: ID of user attempting password change.
    """

    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class UserPasswordChangeSucceeded(DomainEvent):
    """User password change completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record USER_PASSWORD_CHANGED
    - EmailEventHandler: Send password changed notification
    - SessionEventHandler: Revoke all sessions (force re-login)

    Attributes:
        user_id: ID of user whose password changed.
        initiated_by: Who initiated change ("user" or "admin").
    """

    user_id: UUID
    initiated_by: str


@dataclass(frozen=True, kw_only=True)
class UserPasswordChangeFailed(DomainEvent):
    """User password change failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record USER_PASSWORD_CHANGE_FAILED

    Attributes:
        user_id: ID of user attempting password change.
        reason: Failure reason (e.g., "user_not_found", "invalid_password").
    """

    user_id: UUID
    reason: str


# ═══════════════════════════════════════════════════════════════
# Provider Connection (Workflow 5) - Placeholder for Phase 2
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class ProviderConnectionAttempted(DomainEvent):
    """Provider connection attempt initiated (OAuth flow started)."""

    user_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True)
class ProviderConnectionSucceeded(DomainEvent):
    """Provider connected successfully (OAuth completed, tokens saved)."""

    user_id: UUID
    provider_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True)
class ProviderConnectionFailed(DomainEvent):
    """Provider connection failed (OAuth failed, API error)."""

    user_id: UUID
    provider_name: str
    reason: str


# ═══════════════════════════════════════════════════════════════
# Token Refresh (Workflow 6) - Placeholder for Phase 2
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class TokenRefreshAttempted(DomainEvent):
    """Token refresh attempt initiated."""

    user_id: UUID
    provider_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True)
class TokenRefreshSucceeded(DomainEvent):
    """Token refresh completed successfully."""

    user_id: UUID
    provider_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True)
class TokenRefreshFailed(DomainEvent):
    """Token refresh failed (user action required - reconnect provider)."""

    user_id: UUID
    provider_id: UUID
    provider_name: str
    error_code: str
