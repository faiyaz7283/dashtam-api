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
    # Password Reset Events
    PasswordResetConfirmAttempted,
    PasswordResetConfirmFailed,
    PasswordResetConfirmSucceeded,
    PasswordResetRequestAttempted,
    PasswordResetRequestFailed,
    PasswordResetRequestSucceeded,
    # Provider Connection Events
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    # Provider Token Refresh Events (OAuth)
    ProviderTokenRefreshAttempted,
    ProviderTokenRefreshFailed,
    ProviderTokenRefreshSucceeded,
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
        ...     user_id=uuid4(),
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
            event: ProviderConnectionAttempted event with provider name.
        """
        self._logger.info(
            "provider_connection_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_name=event.provider_name,
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
            provider_id=str(event.provider_id),
            provider_name=event.provider_name,
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
            provider_name=event.provider_name,
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
            provider_id=str(event.provider_id),
            provider_name=event.provider_name,
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
            provider_id=str(event.provider_id),
            provider_name=event.provider_name,
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
            provider_id=str(event.provider_id),
            provider_name=event.provider_name,
            error_code=event.error_code,
        )
