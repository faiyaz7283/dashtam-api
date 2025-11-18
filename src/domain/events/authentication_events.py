"""Authentication domain events.

This module defines all domain events related to user authentication workflows.
Following the full event-driven architecture pattern, each critical workflow
emits THREE events representing the complete lifecycle:

    1. ATTEMPTED - Published BEFORE operation (captures intent + context)
    2. SUCCEEDED - Published AFTER successful commit (captures outcome)
    3. FAILED - Published AFTER rollback (captures error for alerting)

This 3-state pattern supports audit semantic accuracy (ATTEMPT → OUTCOME)
required for PCI-DSS compliance while keeping command handlers clean.

Critical Workflows (Phase 1 MVP):
    1. User Registration (UserRegistrationAttempted/Succeeded/Failed)
    2. User Password Change (UserPasswordChangeAttempted/Succeeded/Failed)
    3. Provider Connection (ProviderConnectionAttempted/Succeeded/Failed)
    4. Token Refresh (TokenRefreshAttempted/Succeeded/Failed)

Event Naming Convention:
    - Past tense: UserRegistered (NOT RegisterUser)
    - Pattern: <Entity><Action><State>
    - Examples: UserRegistrationSucceeded, ProviderConnectionFailed

Usage:
    >>> # In command handler: BEFORE operation
    >>> await event_bus.publish(UserRegistrationAttempted(
    ...     email=cmd.email,
    ...     ip_address=ip_address,
    ... ))
    >>>
    >>> # Business logic
    >>> user = User(email=cmd.email, ...)
    >>> await user_repo.save(user)
    >>> await session.commit()
    >>>
    >>> # AFTER successful commit
    >>> await event_bus.publish(UserRegistrationSucceeded(
    ...     user_id=user.id,
    ...     email=user.email,
    ... ))

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 547-723)
    - ~/starter/clean-slate-reference.md Section 9.4 (Domain Events)
"""

from dataclasses import dataclass
from uuid import UUID

from src.domain.events.base_event import DomainEvent


# ============================================================================
# User Registration Events (Workflow 1)
# ============================================================================


@dataclass(frozen=True, kw_only=True, slots=True)
class UserRegistrationAttempted(DomainEvent):
    """User registration was attempted (BEFORE operation).

    Published BEFORE user creation to capture attempt intent and context.
    Used for audit trail semantic accuracy (ATTEMPT → OUTCOME pattern).

    Attributes:
        email: Email address provided in registration attempt. May be invalid
            or already exist (validation happens after this event).
        ip_address: Client IP address for security audit. None if unavailable
            (e.g., internal system registration).

    Event Handlers:
        - LoggingEventHandler: Log attempt with email and IP (info level)
        - AuditEventHandler: Create audit record (USER_REGISTRATION_ATTEMPTED)

    Example:
        >>> # At START of RegisterUserHandler.handle()
        >>> await event_bus.publish(UserRegistrationAttempted(
        ...     email=cmd.email,
        ...     ip_address=request.client.host,
        ... ))
        >>>
        >>> # Then proceed with validation and user creation

    Notes:
        - Published BEFORE validation (may fail due to invalid email, duplicate)
        - No user_id yet (user not created)
        - IP address used for fraud detection and security audit
    """

    email: str
    """Email address provided in registration attempt."""

    ip_address: str | None = None
    """Client IP address for security audit (None if unavailable)."""


@dataclass(frozen=True, kw_only=True, slots=True)
class UserRegistrationSucceeded(DomainEvent):
    """User registration succeeded (AFTER commit).

    Published AFTER successful user creation and database commit. Triggers
    side effects: welcome email, onboarding tasks, analytics tracking.

    Attributes:
        user_id: UUID of newly created user. Used to link audit records and
            track user across all future events.
        email: Verified email address of registered user. Used for welcome
            email and identity verification.

    Event Handlers:
        - LoggingEventHandler: Log success with user_id (info level)
        - AuditEventHandler: Create audit record (USER_REGISTRATION_SUCCEEDED)
        - EmailEventHandler: Send welcome email with verification link (stub)

    Example:
        >>> # After successful commit in RegisterUserHandler
        >>> user = User(email=cmd.email, ...)
        >>> await user_repo.save(user)
        >>> await session.commit()  # ← COMMIT FIRST
        >>>
        >>> await event_bus.publish(UserRegistrationSucceeded(
        ...     user_id=user.id,
        ...     email=user.email,
        ... ))

    Notes:
        - Published AFTER commit (fact, not intent)
        - User guaranteed to exist in database
        - Welcome email sent asynchronously (fail-open)
    """

    user_id: UUID
    """UUID of newly created user."""

    email: str
    """Email address of registered user."""


@dataclass(frozen=True, kw_only=True, slots=True)
class UserRegistrationFailed(DomainEvent):
    """User registration failed (AFTER rollback).

    Published AFTER registration failure and transaction rollback. Used for
    alerting, fraud detection, and failure analytics.

    Attributes:
        email: Email address from failed registration attempt. Used to detect
            brute force attacks or system issues.
        error_code: Machine-readable error code (e.g., "duplicate_email",
            "invalid_email"). Used for analytics and alerting.
        error_message: Human-readable error message for logging and debugging.
        ip_address: Client IP address for fraud detection. None if unavailable.

    Event Handlers:
        - LoggingEventHandler: Log failure with error details (warning level)
        - AuditEventHandler: Create audit record (USER_REGISTRATION_FAILED)

    Example:
        >>> # In RegisterUserHandler exception handler
        >>> try:
        ...     user = User(email=cmd.email, ...)
        ...     await user_repo.save(user)
        ...     await session.commit()
        ... except IntegrityError as e:
        ...     await session.rollback()  # ← ROLLBACK FIRST
        ...
        ...     await event_bus.publish(UserRegistrationFailed(
        ...         email=cmd.email,
        ...         error_code="duplicate_email",
        ...         error_message=str(e),
        ...         ip_address=ip_address,
        ...     ))
        ...     return Failure(ConflictError("Email already registered"))

    Notes:
        - Published AFTER rollback (no database changes)
        - No user_id (user not created)
        - Used for fraud detection (repeated failures from same IP)
    """

    email: str
    """Email address from failed registration attempt."""

    error_code: str
    """Machine-readable error code (e.g., 'duplicate_email')."""

    error_message: str
    """Human-readable error message for logging."""

    ip_address: str | None = None
    """Client IP address for fraud detection (None if unavailable)."""


# ============================================================================
# User Password Change Events (Workflow 2)
# ============================================================================


@dataclass(frozen=True, kw_only=True, slots=True)
class UserPasswordChangeAttempted(DomainEvent):
    """User password change was attempted (BEFORE operation).

    Published BEFORE password change to capture attempt intent. Used for
    security audit and suspicious activity detection.

    Attributes:
        user_id: UUID of user attempting password change. Used to link audit
            records and detect account compromise.
        initiated_by: Who initiated the change ('user' or 'admin'). Used to
            differentiate self-service vs admin-forced password resets.
        ip_address: Client IP address for security audit. None if unavailable.

    Event Handlers:
        - LoggingEventHandler: Log attempt with user_id and initiator (info level)
        - AuditEventHandler: Create audit record (USER_PASSWORD_CHANGE_ATTEMPTED)

    Example:
        >>> # At START of ChangePasswordHandler.handle()
        >>> await event_bus.publish(UserPasswordChangeAttempted(
        ...     user_id=user.id,
        ...     initiated_by='user',
        ...     ip_address=request.client.host,
        ... ))
        >>>
        >>> # Then proceed with validation and password update

    Notes:
        - Published BEFORE validation (may fail due to wrong old password)
        - Used for suspicious activity detection (multiple failed attempts)
        - IP address used to detect account takeover attempts
    """

    user_id: UUID
    """UUID of user attempting password change."""

    initiated_by: str
    """Who initiated change: 'user' (self-service) or 'admin' (forced reset)."""

    ip_address: str | None = None
    """Client IP address for security audit (None if unavailable)."""


@dataclass(frozen=True, kw_only=True, slots=True)
class UserPasswordChangeSucceeded(DomainEvent):
    """User password change succeeded (AFTER commit).

    Published AFTER successful password change and database commit. Triggers
    critical security side effects: session revocation, notification email.

    Attributes:
        user_id: UUID of user whose password was changed. Used to revoke all
            existing sessions (force re-login on all devices).
        initiated_by: Who initiated the change ('user' or 'admin'). Used in
            notification email to alert user of password change.

    Event Handlers:
        - LoggingEventHandler: Log success with user_id (info level)
        - AuditEventHandler: Create audit record (USER_PASSWORD_CHANGE_SUCCEEDED)
        - SessionEventHandler: Revoke all user sessions (force re-login, stub)
        - EmailEventHandler: Send password change notification (stub)

    Example:
        >>> # After successful commit in ChangePasswordHandler
        >>> user.password_hash = hash_password(cmd.new_password)
        >>> await user_repo.save(user)
        >>> await session.commit()  # ← COMMIT FIRST
        >>>
        >>> await event_bus.publish(UserPasswordChangeSucceeded(
        ...     user_id=user.id,
        ...     initiated_by='user',
        ... ))
        >>>
        >>> # Sessions revoked automatically by SessionEventHandler

    Notes:
        - Published AFTER commit (password guaranteed changed)
        - Session revocation prevents unauthorized access
        - Notification email alerts user of security-critical change
    """

    user_id: UUID
    """UUID of user whose password was changed."""

    initiated_by: str
    """Who initiated change: 'user' or 'admin'."""


@dataclass(frozen=True, kw_only=True, slots=True)
class UserPasswordChangeFailed(DomainEvent):
    """User password change failed (AFTER rollback).

    Published AFTER password change failure and transaction rollback. Used for
    security monitoring and account protection (lock after N failures).

    Attributes:
        user_id: UUID of user whose password change failed. Used to track
            failed attempts and trigger account lockout if threshold exceeded.
        initiated_by: Who initiated the change ('user' or 'admin'). Used to
            differentiate self-service vs admin-forced password resets.
        error_code: Machine-readable error code (e.g., "invalid_old_password",
            "weak_password"). Used for analytics and security monitoring.
        error_message: Human-readable error message for logging.
        ip_address: Client IP address for security audit. None if unavailable.

    Event Handlers:
        - LoggingEventHandler: Log failure with error details (warning level)
        - AuditEventHandler: Create audit record (USER_PASSWORD_CHANGE_FAILED)

    Example:
        >>> # In ChangePasswordHandler exception handler
        >>> if not verify_password(cmd.old_password, user.password_hash):
        ...     await event_bus.publish(UserPasswordChangeFailed(
        ...         user_id=user.id,
        ...         initiated_by='user',
        ...         error_code="invalid_old_password",
        ...         error_message="Old password incorrect",
        ...         ip_address=ip_address,
        ...     ))
        ...     return Failure(ValidationError("Old password incorrect"))

    Notes:
        - Published AFTER validation failure (no database changes)
        - Used for account protection (lock after 5 failed attempts)
        - IP tracking detects brute force attacks
    """

    user_id: UUID
    """UUID of user whose password change failed."""

    initiated_by: str
    """Who initiated change: 'user' (self-service) or 'admin' (forced reset)."""

    error_code: str
    """Machine-readable error code (e.g., 'invalid_old_password')."""

    error_message: str
    """Human-readable error message for logging."""

    ip_address: str | None = None
    """Client IP address for security audit (None if unavailable)."""


# ============================================================================
# Provider Connection Events (Workflow 3)
# ============================================================================


@dataclass(frozen=True, kw_only=True, slots=True)
class ProviderConnectionAttempted(DomainEvent):
    """Provider connection was attempted (BEFORE OAuth flow).

    Published BEFORE OAuth authorization redirect to capture attempt intent.
    Used for analytics (conversion tracking) and fraud detection.

    Attributes:
        user_id: UUID of user attempting to connect provider. Used to link
            audit records and track onboarding funnel.
        provider_name: Provider being connected (e.g., 'schwab', 'plaid').
            Used for analytics and failure debugging.
        ip_address: Client IP address for security audit. None if unavailable.

    Event Handlers:
        - LoggingEventHandler: Log attempt with provider name (info level)
        - AuditEventHandler: Create audit record (PROVIDER_CONNECTION_ATTEMPTED)

    Example:
        >>> # At START of ConnectProviderHandler.handle()
        >>> await event_bus.publish(ProviderConnectionAttempted(
        ...     user_id=user.id,
        ...     provider_name='schwab',
        ...     ip_address=request.client.host,
        ... ))
        >>>
        >>> # Then redirect to OAuth authorization URL

    Notes:
        - Published BEFORE OAuth flow (may fail at authorization)
        - No provider_id yet (connection not created)
        - Used for conversion funnel analytics
    """

    user_id: UUID
    """UUID of user attempting to connect provider."""

    provider_name: str
    """Provider being connected (e.g., 'schwab', 'plaid')."""

    ip_address: str | None = None
    """Client IP address for security audit (None if unavailable)."""


@dataclass(frozen=True, kw_only=True, slots=True)
class ProviderConnectionSucceeded(DomainEvent):
    """Provider connection succeeded (AFTER commit).

    Published AFTER successful OAuth token exchange and database commit.
    Triggers data sync: fetch accounts, transactions, holdings.

    Attributes:
        user_id: UUID of user who connected provider. Used for data sync and
            notification.
        provider_id: UUID of newly created provider connection. Used to link
            accounts and transactions to this provider.
        provider_name: Provider that was connected (e.g., 'schwab'). Used for
            analytics and notification email.

    Event Handlers:
        - LoggingEventHandler: Log success with provider_id (info level)
        - AuditEventHandler: Create audit record (PROVIDER_CONNECTION_SUCCEEDED)

    Example:
        >>> # After successful OAuth callback in ConnectProviderHandler
        >>> provider = Provider(user_id=user.id, name='schwab', ...)
        >>> await provider_repo.save(provider)
        >>> await session.commit()  # ← COMMIT FIRST
        >>>
        >>> await event_bus.publish(ProviderConnectionSucceeded(
        ...     user_id=user.id,
        ...     provider_id=provider.id,
        ...     provider_name='schwab',
        ... ))
        >>>
        >>> # Data sync triggered automatically (future implementation)

    Notes:
        - Published AFTER commit (provider guaranteed to exist)
        - Data sync happens asynchronously (accounts, transactions)
        - Used for onboarding completion tracking
    """

    user_id: UUID
    """UUID of user who connected provider."""

    provider_id: UUID
    """UUID of newly created provider connection."""

    provider_name: str
    """Provider that was connected (e.g., 'schwab')."""


@dataclass(frozen=True, kw_only=True, slots=True)
class ProviderConnectionFailed(DomainEvent):
    """Provider connection failed (AFTER OAuth failure).

    Published AFTER OAuth authorization failure or token exchange error.
    Used for alerting, failure analytics, and user support.

    Attributes:
        user_id: UUID of user whose provider connection failed. Used to track
            failure rate and provide user support.
        provider_name: Provider that failed to connect (e.g., 'schwab'). Used
            for analytics and alerting (high failure rate = API issues).
        error_code: Machine-readable error code from OAuth provider (e.g.,
            "access_denied", "invalid_grant"). Used for debugging.
        error_message: Human-readable error message for logging and support.

    Event Handlers:
        - LoggingEventHandler: Log failure with error details (warning level)
        - AuditEventHandler: Create audit record (PROVIDER_CONNECTION_FAILED)

    Example:
        >>> # In ConnectProviderHandler OAuth callback error handler
        >>> try:
        ...     tokens = await oauth_client.exchange_code(code)
        ...     provider = Provider(...)
        ...     await provider_repo.save(provider)
        ...     await session.commit()
        ... except OAuthError as e:
        ...     await event_bus.publish(ProviderConnectionFailed(
        ...         user_id=user.id,
        ...         provider_name='schwab',
        ...         error_code=e.error_code,
        ...         error_message=str(e),
        ...     ))
        ...     return Failure(ExternalServiceError("OAuth failed"))

    Notes:
        - Published AFTER OAuth failure (no database changes)
        - No provider_id (connection not created)
        - Used for alerting (high failure rate indicates API issues)
    """

    user_id: UUID
    """UUID of user whose provider connection failed."""

    provider_name: str
    """Provider that failed to connect (e.g., 'schwab')."""

    error_code: str
    """Machine-readable OAuth error code (e.g., 'access_denied')."""

    error_message: str
    """Human-readable error message for logging."""


# ============================================================================
# Token Refresh Events (Workflow 4)
# ============================================================================


@dataclass(frozen=True, kw_only=True, slots=True)
class TokenRefreshAttempted(DomainEvent):
    """Token refresh was attempted (BEFORE API call).

    Published BEFORE OAuth token refresh API call. Used for monitoring token
    health and proactive alerting on refresh failures.

    Attributes:
        user_id: UUID of user whose token is being refreshed. Used to notify
            user if refresh fails (disconnection imminent).
        provider_id: UUID of provider whose token is being refreshed. Used to
            track token health per provider.
        provider_name: Provider name (e.g., 'schwab'). Used for analytics.

    Event Handlers:
        - LoggingEventHandler: Log attempt with provider name (info level)
        - AuditEventHandler: Create audit record (TOKEN_REFRESH_ATTEMPTED)

    Example:
        >>> # At START of RefreshTokenHandler.handle()
        >>> await event_bus.publish(TokenRefreshAttempted(
        ...     user_id=provider.user_id,
        ...     provider_id=provider.id,
        ...     provider_name='schwab',
        ... ))
        >>>
        >>> # Then call OAuth refresh endpoint

    Notes:
        - Published BEFORE API call (may fail due to revoked token)
        - Used for monitoring token refresh success rate
        - High failure rate indicates OAuth configuration issues
    """

    user_id: UUID
    """UUID of user whose token is being refreshed."""

    provider_id: UUID
    """UUID of provider whose token is being refreshed."""

    provider_name: str
    """Provider name (e.g., 'schwab')."""


@dataclass(frozen=True, kw_only=True, slots=True)
class TokenRefreshSucceeded(DomainEvent):
    """Token refresh succeeded (AFTER commit).

    Published AFTER successful token refresh and database commit. Confirms
    provider connection is still active and healthy.

    Attributes:
        user_id: UUID of user whose token was refreshed. Used for health
            monitoring and analytics.
        provider_id: UUID of provider whose token was refreshed. Used to track
            token refresh cadence and health.
        provider_name: Provider name (e.g., 'schwab'). Used for analytics.

    Event Handlers:
        - LoggingEventHandler: Log success with provider_id (info level)
        - AuditEventHandler: Create audit record (TOKEN_REFRESH_SUCCEEDED)

    Example:
        >>> # After successful token refresh in RefreshTokenHandler
        >>> provider.access_token = new_tokens.access_token
        >>> provider.refresh_token = new_tokens.refresh_token
        >>> await provider_repo.save(provider)
        >>> await session.commit()  # ← COMMIT FIRST
        >>>
        >>> await event_bus.publish(TokenRefreshSucceeded(
        ...     user_id=provider.user_id,
        ...     provider_id=provider.id,
        ...     provider_name='schwab',
        ... ))

    Notes:
        - Published AFTER commit (tokens guaranteed updated)
        - Indicates provider connection is healthy
        - Used for monitoring token refresh patterns
    """

    user_id: UUID
    """UUID of user whose token was refreshed."""

    provider_id: UUID
    """UUID of provider whose token was refreshed."""

    provider_name: str
    """Provider name (e.g., 'schwab')."""


@dataclass(frozen=True, kw_only=True, slots=True)
class TokenRefreshFailed(DomainEvent):
    """Token refresh failed (AFTER API error).

    Published AFTER OAuth token refresh failure. CRITICAL event: triggers
    user notification (provider disconnection imminent) and alerting.

    Attributes:
        user_id: UUID of user whose token refresh failed. Used to send
            notification email: "Please reconnect your Schwab account."
        provider_id: UUID of provider whose token refresh failed. Used to mark
            provider as "needs_reconnection" in database.
        provider_name: Provider name (e.g., 'schwab'). Used for alerting and
            user notification.
        error_code: Machine-readable OAuth error code (e.g., "invalid_grant",
            "revoked_token"). Used for debugging and analytics.
        error_message: Human-readable error message for logging.

    Event Handlers:
        - LoggingEventHandler: Log failure with error details (warning level)
        - AuditEventHandler: Create audit record (TOKEN_REFRESH_FAILED)

    Example:
        >>> # In RefreshTokenHandler OAuth error handler
        >>> try:
        ...     new_tokens = await oauth_client.refresh_token(
        ...         provider.refresh_token
        ...     )
        ...     provider.access_token = new_tokens.access_token
        ...     await provider_repo.save(provider)
        ...     await session.commit()
        ... except OAuthError as e:
        ...     await event_bus.publish(TokenRefreshFailed(
        ...         user_id=provider.user_id,
        ...         provider_id=provider.id,
        ...         provider_name='schwab',
        ...         error_code=e.error_code,
        ...         error_message=str(e),
        ...     ))
        ...     # Mark provider as needs_reconnection
        ...     return Failure(ExternalServiceError("Token refresh failed"))

    Notes:
        - Published AFTER API failure (no database changes)
        - CRITICAL: User must reconnect provider manually
        - High volume indicates OAuth issues or user revocations
    """

    user_id: UUID
    """UUID of user whose token refresh failed."""

    provider_id: UUID
    """UUID of provider whose token refresh failed."""

    provider_name: str
    """Provider name (e.g., 'schwab')."""

    error_code: str
    """Machine-readable OAuth error code (e.g., 'invalid_grant')."""

    error_message: str
    """Human-readable error message for logging."""
