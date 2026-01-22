"""Logging event handler for domain events.

This module implements structured logging for all critical domain events.
Subscribes to 12 authentication events and logs with appropriate severity
levels and structured fields for observability.

Log Levels:
    - INFO: ATTEMPTED and SUCCEEDED events (normal operations)
    - WARNING: FAILED events (operational issues requiring attention)

Structured Fields:
    - event_type: Event class name (e.g., "UserRegistrationSucceeded")
    - event_id: UUID for event correlation and deduplication
    - occurred_at: ISO 8601 timestamp (UTC)
    - user_id: UUID (when available - not for ATTEMPTED events)
    - email: Email address (when available)
    - provider_name: Provider name (for provider events)
    - error_code: Machine-readable error (for FAILED events)

Usage:
    >>> # Container wires up subscriptions at startup
    >>> event_bus = get_event_bus()
    >>> logging_handler = LoggingEventHandler(logger=get_logger())
    >>>
    >>> # Subscribe to all 12 events
    >>> event_bus.subscribe(UserRegistrationAttempted, logging_handler.handle_user_registration_attempted)
    >>> event_bus.subscribe(UserRegistrationSucceeded, logging_handler.handle_user_registration_succeeded)
    >>> # ... and 10 more subscriptions

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 1068-1171)
    - docs/architecture/structured-logging-architecture.md
"""

from src.domain.events.auth_events import (
    # Auth Token Refresh Events (JWT rotation)
    AuthTokenRefreshAttempted,
    AuthTokenRefreshFailed,
    AuthTokenRefreshSucceeded,
    # Email Verification Events
    EmailVerificationAttempted,
    EmailVerificationFailed,
    EmailVerificationSucceeded,
    # Global Token Rotation Events
    GlobalTokenRotationAttempted,
    GlobalTokenRotationFailed,
    GlobalTokenRotationSucceeded,
    # Password Reset Events
    PasswordResetConfirmAttempted,
    PasswordResetConfirmFailed,
    PasswordResetConfirmSucceeded,
    PasswordResetRequestAttempted,
    PasswordResetRequestFailed,
    PasswordResetRequestSucceeded,
    # Token Rejected Due to Rotation
    TokenRejectedDueToRotation,
    # User Login Events
    UserLoginAttempted,
    UserLoginFailed,
    UserLoginSucceeded,
    # User Logout Events
    UserLogoutAttempted,
    UserLogoutFailed,
    UserLogoutSucceeded,
    # User Password Change Events
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
    # User Registration Events
    UserRegistrationAttempted,
    UserRegistrationFailed,
    UserRegistrationSucceeded,
    # User Token Rotation Events
    UserTokenRotationAttempted,
    UserTokenRotationFailed,
    UserTokenRotationSucceeded,
)
from src.domain.events.authorization_events import (
    # Role Assignment Events
    RoleAssignmentAttempted,
    RoleAssignmentFailed,
    RoleAssignmentSucceeded,
    # Role Revocation Events
    RoleRevocationAttempted,
    RoleRevocationFailed,
    RoleRevocationSucceeded,
)
from src.domain.events.provider_events import (
    # Provider Connection Events
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    # Provider Disconnection Events
    ProviderDisconnectionAttempted,
    ProviderDisconnectionFailed,
    ProviderDisconnectionSucceeded,
    # Provider Token Refresh Events (OAuth)
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
)
from src.domain.events.rate_limit_events import (
    # Rate Limit Events
    RateLimitCheckAttempted,
    RateLimitCheckAllowed,
    RateLimitCheckDenied,
)
from src.domain.events.session_events import (
    # Session Events (3-state workflow)
    SessionRevocationAttempted,
    SessionRevokedEvent,
    SessionRevocationFailed,
    AllSessionsRevocationAttempted,
    AllSessionsRevokedEvent,
    AllSessionsRevocationFailed,
    # Session Events (operational)
    SessionCreatedEvent,
    SessionEvictedEvent,
    SessionActivityUpdatedEvent,
    SessionProviderAccessEvent,
    SuspiciousSessionActivityEvent,
    SessionLimitExceededEvent,
)
from src.domain.events.data_events import (
    # Account Sync Events
    AccountSyncAttempted,
    AccountSyncSucceeded,
    AccountSyncFailed,
    # Transaction Sync Events
    TransactionSyncAttempted,
    TransactionSyncSucceeded,
    TransactionSyncFailed,
    # Holdings Sync Events
    HoldingsSyncAttempted,
    HoldingsSyncSucceeded,
    HoldingsSyncFailed,
    # File Import Events (3-state + operational)
    FileImportAttempted,
    FileImportSucceeded,
    FileImportFailed,
    FileImportProgress,
)
from src.domain.protocols.logger_protocol import LoggerProtocol


class LoggingEventHandler:
    """Event handler for structured logging of domain events.

    Subscribes to all critical authentication events and logs with structured
    fields for observability. Uses appropriate log levels: INFO for normal
    operations (ATTEMPTED, SUCCEEDED), WARNING for failures.

    Attributes:
        _logger: Logger protocol implementation (from container).

    Example:
        >>> # Create handler
        >>> handler = LoggingEventHandler(logger=get_logger())
        >>>
        >>> # Subscribe to events (in container)
        >>> event_bus.subscribe(UserRegistrationSucceeded, handler.handle_user_registration_succeeded)
        >>>
        >>> # Events automatically logged when published
        >>> await event_bus.publish(UserRegistrationSucceeded(
        ...     user_id=uuid7(),
        ...     email="test@example.com"
        ... ))
        >>> # Log output: {"event": "user_registration_succeeded", "user_id": "...", "email": "..."}
    """

    def __init__(self, logger: LoggerProtocol) -> None:
        """Initialize logging handler with logger.

        Args:
            logger: Logger protocol implementation from container. Used for
                structured logging with appropriate severity levels.

        Example:
            >>> from src.core.container import get_logger
            >>> logger = get_logger()
            >>> handler = LoggingEventHandler(logger=logger)
        """
        self._logger = logger

    # =========================================================================
    # User Registration Event Handlers
    # =========================================================================

    async def handle_user_registration_attempted(
        self,
        event: UserRegistrationAttempted,
    ) -> None:
        """Log user registration attempt (INFO level).

        Args:
            event: UserRegistrationAttempted event with email.
        """
        self._logger.info(
            "user_registration_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            email=event.email,
        )

    async def handle_user_registration_succeeded(
        self,
        event: UserRegistrationSucceeded,
    ) -> None:
        """Log successful user registration (INFO level).

        Args:
            event: UserRegistrationSucceeded event with user_id and email.
        """
        self._logger.info(
            "user_registration_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            email=event.email,
        )

    async def handle_user_registration_failed(
        self,
        event: UserRegistrationFailed,
    ) -> None:
        """Log failed user registration (WARNING level).

        Args:
            event: UserRegistrationFailed event with error details.
        """
        self._logger.warning(
            "user_registration_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            email=event.email,
            reason=event.reason,
        )

    # =========================================================================
    # User Password Change Event Handlers
    # =========================================================================

    async def handle_user_password_change_attempted(
        self,
        event: UserPasswordChangeAttempted,
    ) -> None:
        """Log password change attempt (INFO level).

        Args:
            event: UserPasswordChangeAttempted event with user_id.
        """
        self._logger.info(
            "user_password_change_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
        )

    async def handle_user_password_change_succeeded(
        self,
        event: UserPasswordChangeSucceeded,
    ) -> None:
        """Log successful password change (INFO level).

        Args:
            event: UserPasswordChangeSucceeded event with user_id.
        """
        self._logger.info(
            "user_password_change_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            initiated_by=event.initiated_by,
        )

    async def handle_user_password_change_failed(
        self,
        event: UserPasswordChangeFailed,
    ) -> None:
        """Log failed password change (WARNING level).

        Args:
            event: UserPasswordChangeFailed event with error details.
        """
        self._logger.warning(
            "user_password_change_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            reason=event.reason,
        )

    # =========================================================================
    # Provider Connection Event Handlers
    # =========================================================================

    async def handle_provider_connection_attempted(
        self,
        event: ProviderConnectionAttempted,
    ) -> None:
        """Log provider connection attempt (INFO level).

        Args:
            event: ProviderConnectionAttempted event with provider slug.
        """
        self._logger.info(
            "provider_connection_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
        )

    async def handle_provider_connection_succeeded(
        self,
        event: ProviderConnectionSucceeded,
    ) -> None:
        """Log successful provider connection (INFO level).

        Args:
            event: ProviderConnectionSucceeded event with provider_id.
        """
        self._logger.info(
            "provider_connection_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
        )

    async def handle_provider_connection_failed(
        self,
        event: ProviderConnectionFailed,
    ) -> None:
        """Log failed provider connection (WARNING level).

        Args:
            event: ProviderConnectionFailed event with error details.
        """
        self._logger.warning(
            "provider_connection_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
            reason=event.reason,
        )

    # =========================================================================
    # User Login Event Handlers
    # =========================================================================

    async def handle_user_login_attempted(
        self,
        event: UserLoginAttempted,
    ) -> None:
        """Log user login attempt (INFO level)."""
        self._logger.info(
            "user_login_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            email=event.email,
        )

    async def handle_user_login_succeeded(
        self,
        event: UserLoginSucceeded,
    ) -> None:
        """Log successful user login (INFO level)."""
        self._logger.info(
            "user_login_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            email=event.email,
            session_id=str(event.session_id) if event.session_id else None,
        )

    async def handle_user_login_failed(
        self,
        event: UserLoginFailed,
    ) -> None:
        """Log failed user login (WARNING level)."""
        self._logger.warning(
            "user_login_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            email=event.email,
            reason=event.reason,
            user_id=str(event.user_id) if event.user_id else None,
        )

    # =========================================================================
    # User Logout Event Handlers
    # =========================================================================

    async def handle_user_logout_attempted(
        self,
        event: UserLogoutAttempted,
    ) -> None:
        """Log user logout attempt (INFO level)."""
        self._logger.info(
            "user_logout_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
        )

    async def handle_user_logout_succeeded(
        self,
        event: UserLogoutSucceeded,
    ) -> None:
        """Log successful user logout (INFO level)."""
        self._logger.info(
            "user_logout_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            session_id=str(event.session_id) if event.session_id else None,
        )

    async def handle_user_logout_failed(
        self,
        event: UserLogoutFailed,
    ) -> None:
        """Log failed user logout (WARNING level)."""
        self._logger.warning(
            "user_logout_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            reason=event.reason,
        )

    # =========================================================================
    # Email Verification Event Handlers
    # =========================================================================

    async def handle_email_verification_attempted(
        self,
        event: EmailVerificationAttempted,
    ) -> None:
        """Log email verification attempt (INFO level)."""
        self._logger.info(
            "email_verification_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            token=event.token,
        )

    async def handle_email_verification_succeeded(
        self,
        event: EmailVerificationSucceeded,
    ) -> None:
        """Log successful email verification (INFO level)."""
        self._logger.info(
            "email_verification_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            email=event.email,
        )

    async def handle_email_verification_failed(
        self,
        event: EmailVerificationFailed,
    ) -> None:
        """Log failed email verification (WARNING level)."""
        self._logger.warning(
            "email_verification_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            token=event.token,
            reason=event.reason,
        )

    # =========================================================================
    # Auth Token Refresh Event Handlers (JWT rotation)
    # =========================================================================

    async def handle_auth_token_refresh_attempted(
        self,
        event: AuthTokenRefreshAttempted,
    ) -> None:
        """Log auth token refresh attempt (INFO level)."""
        self._logger.info(
            "auth_token_refresh_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id) if event.user_id else None,
        )

    async def handle_auth_token_refresh_succeeded(
        self,
        event: AuthTokenRefreshSucceeded,
    ) -> None:
        """Log successful auth token refresh (INFO level)."""
        self._logger.info(
            "auth_token_refresh_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            session_id=str(event.session_id),
        )

    async def handle_auth_token_refresh_failed(
        self,
        event: AuthTokenRefreshFailed,
    ) -> None:
        """Log failed auth token refresh (WARNING level)."""
        self._logger.warning(
            "auth_token_refresh_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id) if event.user_id else None,
            reason=event.reason,
        )

    # =========================================================================
    # Password Reset Request Event Handlers
    # =========================================================================

    async def handle_password_reset_request_attempted(
        self,
        event: PasswordResetRequestAttempted,
    ) -> None:
        """Log password reset request attempt (INFO level)."""
        self._logger.info(
            "password_reset_request_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            email=event.email,
        )

    async def handle_password_reset_request_succeeded(
        self,
        event: PasswordResetRequestSucceeded,
    ) -> None:
        """Log successful password reset request (INFO level)."""
        self._logger.info(
            "password_reset_request_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            email=event.email,
        )

    async def handle_password_reset_request_failed(
        self,
        event: PasswordResetRequestFailed,
    ) -> None:
        """Log failed password reset request (WARNING level)."""
        self._logger.warning(
            "password_reset_request_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            email=event.email,
            reason=event.reason,
        )

    # =========================================================================
    # Password Reset Confirm Event Handlers
    # =========================================================================

    async def handle_password_reset_confirm_attempted(
        self,
        event: PasswordResetConfirmAttempted,
    ) -> None:
        """Log password reset confirm attempt (INFO level)."""
        self._logger.info(
            "password_reset_confirm_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            token=event.token,
        )

    async def handle_password_reset_confirm_succeeded(
        self,
        event: PasswordResetConfirmSucceeded,
    ) -> None:
        """Log successful password reset confirm (INFO level)."""
        self._logger.info(
            "password_reset_confirm_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            email=event.email,
        )

    async def handle_password_reset_confirm_failed(
        self,
        event: PasswordResetConfirmFailed,
    ) -> None:
        """Log failed password reset confirm (WARNING level)."""
        self._logger.warning(
            "password_reset_confirm_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            token=event.token,
            reason=event.reason,
        )

    # =========================================================================
    # Provider Token Refresh Event Handlers (OAuth)
    # =========================================================================

    async def handle_provider_token_refresh_attempted(
        self,
        event: ProviderTokenRefreshAttempted,
    ) -> None:
        """Log provider token refresh attempt (INFO level)."""
        self._logger.info(
            "provider_token_refresh_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
        )

    async def handle_provider_token_refresh_succeeded(
        self,
        event: ProviderTokenRefreshSucceeded,
    ) -> None:
        """Log successful provider token refresh (INFO level)."""
        self._logger.info(
            "provider_token_refresh_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
        )

    async def handle_provider_token_refresh_failed(
        self,
        event: ProviderTokenRefreshFailed,
    ) -> None:
        """Log failed provider token refresh (WARNING level)."""
        self._logger.warning(
            "provider_token_refresh_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
            reason=event.reason,
            needs_user_action=event.needs_user_action,
        )

    # =========================================================================
    # Token Rejected Due to Rotation (Security Monitoring)
    # =========================================================================

    async def handle_token_rejected_due_to_rotation(
        self,
        event: TokenRejectedDueToRotation,
    ) -> None:
        """Log token rejection due to version mismatch (WARNING level).

        Security monitoring event for token rotation enforcement.
        """
        self._logger.warning(
            "token_rejected_due_to_rotation",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id) if event.user_id else None,
            token_version=event.token_version,
            required_version=event.required_version,
            rejection_reason=event.rejection_reason,
        )

    # =========================================================================
    # Global Token Rotation Event Handlers
    # =========================================================================

    async def handle_global_token_rotation_attempted(
        self,
        event: GlobalTokenRotationAttempted,
    ) -> None:
        """Log global token rotation attempt (INFO level)."""
        self._logger.info(
            "global_token_rotation_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            triggered_by=event.triggered_by,
            reason=event.reason,
        )

    async def handle_global_token_rotation_succeeded(
        self,
        event: GlobalTokenRotationSucceeded,
    ) -> None:
        """Log successful global token rotation (INFO level)."""
        self._logger.info(
            "global_token_rotation_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            triggered_by=event.triggered_by,
            previous_version=event.previous_version,
            new_version=event.new_version,
            reason=event.reason,
            grace_period_seconds=event.grace_period_seconds,
        )

    async def handle_global_token_rotation_failed(
        self,
        event: GlobalTokenRotationFailed,
    ) -> None:
        """Log failed global token rotation (WARNING level)."""
        self._logger.warning(
            "global_token_rotation_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            triggered_by=event.triggered_by,
            reason=event.reason,
            failure_reason=event.failure_reason,
        )

    # =========================================================================
    # User Token Rotation Event Handlers
    # =========================================================================

    async def handle_user_token_rotation_attempted(
        self,
        event: UserTokenRotationAttempted,
    ) -> None:
        """Log user token rotation attempt (INFO level)."""
        self._logger.info(
            "user_token_rotation_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            triggered_by=event.triggered_by,
            reason=event.reason,
        )

    async def handle_user_token_rotation_succeeded(
        self,
        event: UserTokenRotationSucceeded,
    ) -> None:
        """Log successful user token rotation (INFO level)."""
        self._logger.info(
            "user_token_rotation_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            triggered_by=event.triggered_by,
            previous_version=event.previous_version,
            new_version=event.new_version,
            reason=event.reason,
        )

    async def handle_user_token_rotation_failed(
        self,
        event: UserTokenRotationFailed,
    ) -> None:
        """Log failed user token rotation (WARNING level)."""
        self._logger.warning(
            "user_token_rotation_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            triggered_by=event.triggered_by,
            reason=event.reason,
            failure_reason=event.failure_reason,
        )

    # =========================================================================
    # Role Assignment Event Handlers
    # =========================================================================

    async def handle_role_assignment_attempted(
        self,
        event: RoleAssignmentAttempted,
    ) -> None:
        """Log role assignment attempt (INFO level)."""
        self._logger.info(
            "role_assignment_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            role=event.role,
            assigned_by=str(event.assigned_by),
        )

    async def handle_role_assignment_succeeded(
        self,
        event: RoleAssignmentSucceeded,
    ) -> None:
        """Log successful role assignment (INFO level)."""
        self._logger.info(
            "role_assignment_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            role=event.role,
            assigned_by=str(event.assigned_by),
        )

    async def handle_role_assignment_failed(
        self,
        event: RoleAssignmentFailed,
    ) -> None:
        """Log failed role assignment (WARNING level)."""
        self._logger.warning(
            "role_assignment_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            role=event.role,
            assigned_by=str(event.assigned_by),
            reason=event.reason,
        )

    # =========================================================================
    # Role Revocation Event Handlers
    # =========================================================================

    async def handle_role_revocation_attempted(
        self,
        event: RoleRevocationAttempted,
    ) -> None:
        """Log role revocation attempt (INFO level)."""
        self._logger.info(
            "role_revocation_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            role=event.role,
            revoked_by=str(event.revoked_by),
            reason=event.reason,
        )

    async def handle_role_revocation_succeeded(
        self,
        event: RoleRevocationSucceeded,
    ) -> None:
        """Log successful role revocation (INFO level)."""
        self._logger.info(
            "role_revocation_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            role=event.role,
            revoked_by=str(event.revoked_by),
            reason=event.reason,
        )

    async def handle_role_revocation_failed(
        self,
        event: RoleRevocationFailed,
    ) -> None:
        """Log failed role revocation (WARNING level)."""
        self._logger.warning(
            "role_revocation_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            role=event.role,
            revoked_by=str(event.revoked_by),
            reason=event.reason,
        )

    # =========================================================================
    # Provider Disconnection Event Handlers
    # =========================================================================

    async def handle_provider_disconnection_attempted(
        self,
        event: ProviderDisconnectionAttempted,
    ) -> None:
        """Log provider disconnection attempt (INFO level)."""
        self._logger.info(
            "provider_disconnection_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
        )

    async def handle_provider_disconnection_succeeded(
        self,
        event: ProviderDisconnectionSucceeded,
    ) -> None:
        """Log successful provider disconnection (INFO level)."""
        self._logger.info(
            "provider_disconnection_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
        )

    async def handle_provider_disconnection_failed(
        self,
        event: ProviderDisconnectionFailed,
    ) -> None:
        """Log failed provider disconnection (WARNING level)."""
        self._logger.warning(
            "provider_disconnection_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            provider_id=str(event.provider_id),
            provider_slug=event.provider_slug,
            reason=event.reason,
        )

    # =========================================================================
    # Token Rejected Due to Rotation Event Handlers (F7.7 Phase 4)
    # =========================================================================

    async def handle_token_rejected_due_to_rotation_operational(
        self,
        event: TokenRejectedDueToRotation,
    ) -> None:
        """Log token rejection due to version mismatch (WARNING level - security event)."""
        self._logger.warning(
            "token_rejected_due_to_rotation",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id) if event.user_id else None,
            token_version=event.token_version,
            required_version=event.required_version,
            rejection_reason=event.rejection_reason,
        )

    # =========================================================================
    # Rate Limit Event Handlers (F7.7 Phase 4)
    # =========================================================================

    async def handle_rate_limit_check_attempted(
        self,
        event: RateLimitCheckAttempted,
    ) -> None:
        """Log rate limit check attempt (INFO level)."""
        self._logger.info(
            "rate_limit_check_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            identifier=event.identifier,
            scope=event.scope,
            endpoint=event.endpoint,
        )

    async def handle_rate_limit_check_allowed(
        self,
        event: RateLimitCheckAllowed,
    ) -> None:
        """Log rate limit check allowed (INFO level)."""
        self._logger.info(
            "rate_limit_check_allowed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            identifier=event.identifier,
            scope=event.scope,
            endpoint=event.endpoint,
            remaining_tokens=event.remaining_tokens,
        )

    async def handle_rate_limit_check_denied(
        self,
        event: RateLimitCheckDenied,
    ) -> None:
        """Log rate limit check denied (WARNING level - security event)."""
        self._logger.warning(
            "rate_limit_check_denied",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            identifier=event.identifier,
            scope=event.scope,
            endpoint=event.endpoint,
            retry_after=event.retry_after,
        )

    # =========================================================================
    # Session Event Handlers (F7.7 Phase 4 - Operational Events)
    # =========================================================================

    async def handle_session_created_operational(
        self,
        event: SessionCreatedEvent,
    ) -> None:
        """Log session creation (INFO level)."""
        self._logger.info(
            "session_created",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
            user_id=str(event.user_id),
        )

    async def handle_session_revocation_attempted(
        self,
        event: SessionRevocationAttempted,
    ) -> None:
        """Log session revocation attempt (INFO level)."""
        self._logger.info(
            "session_revocation_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
            user_id=str(event.user_id),
            reason=event.reason,
        )

    async def handle_session_revocation_succeeded(
        self,
        event: SessionRevokedEvent,
    ) -> None:
        """Log session revocation success (WARNING level - security event)."""
        self._logger.warning(
            "session_revoked",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
            user_id=str(event.user_id),
            revoked_by_user=event.revoked_by_user,
            reason=event.reason,
        )

    async def handle_session_revocation_failed(
        self,
        event: SessionRevocationFailed,
    ) -> None:
        """Log session revocation failure (WARNING level)."""
        self._logger.warning(
            "session_revocation_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
            user_id=str(event.user_id),
            reason=event.reason,
            failure_reason=event.failure_reason,
        )

    async def handle_session_evicted_operational(
        self,
        event: SessionEvictedEvent,
    ) -> None:
        """Log session eviction (WARNING level - limit enforcement)."""
        self._logger.warning(
            "session_evicted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
            user_id=str(event.user_id),
            reason=event.reason,
        )

    async def handle_all_sessions_revocation_attempted(
        self,
        event: AllSessionsRevocationAttempted,
    ) -> None:
        """Log all sessions revocation attempt (INFO level)."""
        self._logger.info(
            "all_sessions_revocation_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            reason=event.reason,
        )

    async def handle_all_sessions_revocation_succeeded(
        self,
        event: AllSessionsRevokedEvent,
    ) -> None:
        """Log all sessions revoked success (WARNING level - security event)."""
        self._logger.warning(
            "all_sessions_revoked",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            reason=event.reason,
            session_count=event.session_count,
        )

    async def handle_all_sessions_revocation_failed(
        self,
        event: AllSessionsRevocationFailed,
    ) -> None:
        """Log all sessions revocation failure (WARNING level)."""
        self._logger.warning(
            "all_sessions_revocation_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            reason=event.reason,
            failure_reason=event.failure_reason,
        )

    async def handle_session_activity_updated_operational(
        self,
        event: SessionActivityUpdatedEvent,
    ) -> None:
        """Log session activity update (INFO level - lightweight telemetry)."""
        self._logger.info(
            "session_activity_updated",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
        )

    async def handle_session_provider_access_operational(
        self,
        event: SessionProviderAccessEvent,
    ) -> None:
        """Log session provider access (INFO level - audit trail)."""
        self._logger.info(
            "session_provider_access",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
            user_id=str(event.user_id),
            provider_name=event.provider_name,
        )

    async def handle_suspicious_session_activity_operational(
        self,
        event: SuspiciousSessionActivityEvent,
    ) -> None:
        """Log suspicious session activity (WARNING level - security alert)."""
        self._logger.warning(
            "suspicious_session_activity",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            session_id=str(event.session_id),
            user_id=str(event.user_id),
            activity_type=event.activity_type,
        )

    async def handle_session_limit_exceeded_operational(
        self,
        event: SessionLimitExceededEvent,
    ) -> None:
        """Log session limit exceeded (INFO level - informational)."""
        self._logger.info(
            "session_limit_exceeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            current_count=event.current_count,
            max_sessions=event.max_sessions,
        )

    # =========================================================================
    # Data Sync Event Handlers (F7.7 Phase 4)
    # =========================================================================

    # Account Sync Handlers
    async def handle_account_sync_attempted(
        self,
        event: AccountSyncAttempted,
    ) -> None:
        """Log account sync attempt (INFO level)."""
        self._logger.info(
            "account_sync_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
        )

    async def handle_account_sync_succeeded(
        self,
        event: AccountSyncSucceeded,
    ) -> None:
        """Log successful account sync (INFO level)."""
        self._logger.info(
            "account_sync_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            account_count=event.account_count,
        )

    async def handle_account_sync_failed(
        self,
        event: AccountSyncFailed,
    ) -> None:
        """Log failed account sync (WARNING level)."""
        self._logger.warning(
            "account_sync_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            reason=event.reason,
        )

    # Transaction Sync Handlers
    async def handle_transaction_sync_attempted(
        self,
        event: TransactionSyncAttempted,
    ) -> None:
        """Log transaction sync attempt (INFO level)."""
        self._logger.info(
            "transaction_sync_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            account_id=str(event.account_id) if event.account_id else None,
        )

    async def handle_transaction_sync_succeeded(
        self,
        event: TransactionSyncSucceeded,
    ) -> None:
        """Log successful transaction sync (INFO level)."""
        self._logger.info(
            "transaction_sync_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            account_id=str(event.account_id) if event.account_id else None,
            transaction_count=event.transaction_count,
        )

    async def handle_transaction_sync_failed(
        self,
        event: TransactionSyncFailed,
    ) -> None:
        """Log failed transaction sync (WARNING level)."""
        self._logger.warning(
            "transaction_sync_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            connection_id=str(event.connection_id),
            account_id=str(event.account_id) if event.account_id else None,
            reason=event.reason,
        )

    # Holdings Sync Handlers
    async def handle_holdings_sync_attempted(
        self,
        event: HoldingsSyncAttempted,
    ) -> None:
        """Log holdings sync attempt (INFO level)."""
        self._logger.info(
            "holdings_sync_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            account_id=str(event.account_id),
        )

    async def handle_holdings_sync_succeeded(
        self,
        event: HoldingsSyncSucceeded,
    ) -> None:
        """Log successful holdings sync (INFO level)."""
        self._logger.info(
            "holdings_sync_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            account_id=str(event.account_id),
            holding_count=event.holding_count,
        )

    async def handle_holdings_sync_failed(
        self,
        event: HoldingsSyncFailed,
    ) -> None:
        """Log failed holdings sync (WARNING level)."""
        self._logger.warning(
            "holdings_sync_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            account_id=str(event.account_id),
            reason=event.reason,
        )

    # File Import Handlers
    async def handle_file_import_attempted(
        self,
        event: FileImportAttempted,
    ) -> None:
        """Log file import attempt (INFO level)."""
        self._logger.info(
            "file_import_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_slug=event.provider_slug,
            file_name=event.file_name,
            file_format=event.file_format,
        )

    async def handle_file_import_succeeded(
        self,
        event: FileImportSucceeded,
    ) -> None:
        """Log successful file import (INFO level)."""
        self._logger.info(
            "file_import_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_slug=event.provider_slug,
            file_name=event.file_name,
            file_format=event.file_format,
            account_count=event.account_count,
            transaction_count=event.transaction_count,
        )

    async def handle_file_import_failed(
        self,
        event: FileImportFailed,
    ) -> None:
        """Log failed file import (WARNING level)."""
        self._logger.warning(
            "file_import_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_slug=event.provider_slug,
            file_name=event.file_name,
            file_format=event.file_format,
            reason=event.reason,
        )

    async def handle_file_import_operational(
        self,
        event: FileImportProgress,
    ) -> None:
        """Log file import progress (DEBUG level).

        Method name follows auto-wiring pattern: handle_{workflow_name}_{phase}
        FileImportProgress uses workflow_name='file_import' + phase=OPERATIONAL.

        Uses DEBUG level since progress events are high-frequency during
        large imports and primarily used for real-time SSE updates.
        """
        self._logger.debug(
            "file_import_progress",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_slug=event.provider_slug,
            file_name=event.file_name,
            file_format=event.file_format,
            progress_percent=event.progress_percent,
            records_processed=event.records_processed,
            total_records=event.total_records,
        )
