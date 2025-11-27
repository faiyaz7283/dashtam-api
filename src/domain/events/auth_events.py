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
# Auth Token Refresh (Workflow 6) - JWT/Refresh Token Rotation
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class AuthTokenRefreshAttempted(DomainEvent):
    """Auth token refresh attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record AUTH_TOKEN_REFRESH_ATTEMPTED

    Attributes:
        user_id: User requesting refresh (if known from token).
    """

    user_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class AuthTokenRefreshSucceeded(DomainEvent):
    """Auth token refresh completed successfully (rotation done).

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record AUTH_TOKEN_REFRESHED

    Attributes:
        user_id: User whose tokens were refreshed.
        session_id: Session associated with token.
    """

    user_id: UUID
    session_id: UUID


@dataclass(frozen=True, kw_only=True)
class AuthTokenRefreshFailed(DomainEvent):
    """Auth token refresh failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record AUTH_TOKEN_REFRESH_FAILED

    Attributes:
        user_id: User requesting refresh (if known).
        reason: Failure reason (e.g., "token_expired", "token_revoked",
            "token_invalid", "user_not_found").
    """

    user_id: UUID | None = None
    reason: str


# ═══════════════════════════════════════════════════════════════
# User Logout (Workflow 7)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class UserLogoutAttempted(DomainEvent):
    """User logout attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record USER_LOGOUT_ATTEMPTED

    Attributes:
        user_id: User attempting logout.
    """

    user_id: UUID


@dataclass(frozen=True, kw_only=True)
class UserLogoutSucceeded(DomainEvent):
    """User logout completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record USER_LOGGED_OUT

    Attributes:
        user_id: User who logged out.
        session_id: Session that was terminated.
    """

    user_id: UUID
    session_id: UUID | None = None


@dataclass(frozen=True, kw_only=True)
class UserLogoutFailed(DomainEvent):
    """User logout failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record USER_LOGOUT_FAILED

    Attributes:
        user_id: User attempting logout.
        reason: Failure reason.
    """

    user_id: UUID
    reason: str


# ═══════════════════════════════════════════════════════════════
# Password Reset (Workflow 8)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class PasswordResetRequestAttempted(DomainEvent):
    """Password reset request attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record PASSWORD_RESET_REQUEST_ATTEMPTED

    Attributes:
        email: Email address for reset request.
    """

    email: str


@dataclass(frozen=True, kw_only=True)
class PasswordResetRequestSucceeded(DomainEvent):
    """Password reset request completed (email sent).

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record PASSWORD_RESET_REQUESTED
    - EmailEventHandler: Send password reset email

    Attributes:
        user_id: User requesting reset.
        email: User's email address.
        reset_token: Password reset token (for email handler).
    """

    user_id: UUID
    email: str
    reset_token: str


@dataclass(frozen=True, kw_only=True)
class PasswordResetRequestFailed(DomainEvent):
    """Password reset request failed.

    Note: This event is only logged internally. API always returns success
    to prevent user enumeration.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record PASSWORD_RESET_REQUEST_FAILED (internal only)

    Attributes:
        email: Email address attempted.
        reason: Failure reason (e.g., "user_not_found").
    """

    email: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class PasswordResetConfirmAttempted(DomainEvent):
    """Password reset confirmation attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record PASSWORD_RESET_CONFIRM_ATTEMPTED

    Attributes:
        token: Password reset token (truncated for security).
    """

    token: str  # First 8 chars only for logging


@dataclass(frozen=True, kw_only=True)
class PasswordResetConfirmSucceeded(DomainEvent):
    """Password reset confirmation completed (password updated).

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record PASSWORD_RESET_COMPLETED
    - EmailEventHandler: Send password changed notification
    - SessionEventHandler: Revoke all sessions (force re-login)

    Attributes:
        user_id: User whose password was reset.
        email: User's email address.
    """

    user_id: UUID
    email: str


@dataclass(frozen=True, kw_only=True)
class PasswordResetConfirmFailed(DomainEvent):
    """Password reset confirmation failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record PASSWORD_RESET_CONFIRM_FAILED

    Attributes:
        token: Password reset token (truncated for security).
        reason: Failure reason (e.g., "token_expired", "token_not_found").
    """

    token: str  # First 8 chars only for logging
    reason: str


# ═══════════════════════════════════════════════════════════════
# Provider Token Refresh (Workflow 9) - Placeholder for Phase 2
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class ProviderTokenRefreshAttempted(DomainEvent):
    """Provider token refresh attempt initiated."""

    user_id: UUID
    provider_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True)
class ProviderTokenRefreshSucceeded(DomainEvent):
    """Provider token refresh completed successfully."""

    user_id: UUID
    provider_id: UUID
    provider_name: str


@dataclass(frozen=True, kw_only=True)
class ProviderTokenRefreshFailed(DomainEvent):
    """Provider token refresh failed (user action required - reconnect provider)."""

    user_id: UUID
    provider_id: UUID
    provider_name: str
    error_code: str


# ═══════════════════════════════════════════════════════════════
# Global Token Rotation (Workflow 10)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class GlobalTokenRotationAttempted(DomainEvent):
    """Global token rotation attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record GLOBAL_TOKEN_ROTATION_ATTEMPTED

    Attributes:
        triggered_by: Who triggered rotation (admin user ID or "system").
        reason: Why rotation is being triggered.
    """

    triggered_by: str  # User ID or "system"
    reason: str


@dataclass(frozen=True, kw_only=True)
class GlobalTokenRotationSucceeded(DomainEvent):
    """Global token rotation completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record GLOBAL_TOKEN_ROTATION_SUCCEEDED

    Attributes:
        triggered_by: Who triggered rotation (admin user ID or "system").
        previous_version: Previous global minimum token version.
        new_version: New global minimum token version.
        reason: Why rotation was triggered.
        grace_period_seconds: Grace period before full enforcement.
    """

    triggered_by: str  # User ID or "system"
    previous_version: int
    new_version: int
    reason: str
    grace_period_seconds: int


@dataclass(frozen=True, kw_only=True)
class GlobalTokenRotationFailed(DomainEvent):
    """Global token rotation failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record GLOBAL_TOKEN_ROTATION_FAILED

    Attributes:
        triggered_by: Who triggered rotation (admin user ID or "system").
        reason: Original reason for rotation attempt.
        failure_reason: Why rotation failed (e.g., "config_not_found").
    """

    triggered_by: str  # User ID or "system"
    reason: str
    failure_reason: str


# ═══════════════════════════════════════════════════════════════
# Per-User Token Rotation (Workflow 11)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class UserTokenRotationAttempted(DomainEvent):
    """Per-user token rotation attempt initiated.

    Triggers:
    - LoggingEventHandler: Log attempt
    - AuditEventHandler: Record USER_TOKEN_ROTATION_ATTEMPTED

    Attributes:
        user_id: User whose tokens are being rotated.
        triggered_by: Who triggered rotation (user_id, admin_id, or "system").
        reason: Why rotation is being triggered.
    """

    user_id: UUID
    triggered_by: str  # User ID, admin ID, or "system"
    reason: str


@dataclass(frozen=True, kw_only=True)
class UserTokenRotationSucceeded(DomainEvent):
    """Per-user token rotation completed successfully.

    Triggers:
    - LoggingEventHandler: Log success
    - AuditEventHandler: Record USER_TOKEN_ROTATION_SUCCEEDED

    Attributes:
        user_id: User whose tokens were rotated.
        triggered_by: Who triggered rotation (user_id, admin_id, or "system").
        previous_version: Previous user minimum token version.
        new_version: New user minimum token version.
        reason: Why rotation was triggered.
    """

    user_id: UUID
    triggered_by: str  # User ID, admin ID, or "system"
    previous_version: int
    new_version: int
    reason: str


@dataclass(frozen=True, kw_only=True)
class UserTokenRotationFailed(DomainEvent):
    """Per-user token rotation failed.

    Triggers:
    - LoggingEventHandler: Log failure
    - AuditEventHandler: Record USER_TOKEN_ROTATION_FAILED

    Attributes:
        user_id: User whose tokens were being rotated.
        triggered_by: Who triggered rotation (user_id, admin_id, or "system").
        reason: Original reason for rotation attempt.
        failure_reason: Why rotation failed (e.g., "user_not_found").
    """

    user_id: UUID
    triggered_by: str  # User ID, admin ID, or "system"
    reason: str
    failure_reason: str


# ═══════════════════════════════════════════════════════════════
# Token Version Validation (Security Monitoring)
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True, kw_only=True)
class TokenRejectedDueToRotation(DomainEvent):
    """Token rejected because it failed version validation.

    This is a security monitoring event, not a user workflow.
    Emitted during token refresh when version check fails.

    Triggers:
    - LoggingEventHandler: Log rejection (security monitoring)
    - AuditEventHandler: Record TOKEN_REJECTED_VERSION_MISMATCH

    Attributes:
        user_id: User whose token was rejected (if known).
        token_version: Version of the rejected token.
        required_version: Minimum version required.
        rejection_reason: Why token was rejected (global_rotation, user_rotation).
    """

    user_id: UUID | None
    token_version: int
    required_version: int
    rejection_reason: str
