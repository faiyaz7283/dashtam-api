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
    ProviderConnectionAttempted,
    ProviderConnectionFailed,
    ProviderConnectionSucceeded,
    TokenRefreshAttempted,
    TokenRefreshFailed,
    TokenRefreshSucceeded,
    UserPasswordChangeAttempted,
    UserPasswordChangeFailed,
    UserPasswordChangeSucceeded,
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
    # Token Refresh Event Handlers
    # =========================================================================

    async def handle_token_refresh_attempted(
        self,
        event: TokenRefreshAttempted,
    ) -> None:
        """Log token refresh attempt (INFO level).

        Args:
            event: TokenRefreshAttempted event with provider details.
        """
        self._logger.info(
            "token_refresh_attempted",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_id=str(event.provider_id),
            provider_name=event.provider_name,
        )

    async def handle_token_refresh_succeeded(
        self,
        event: TokenRefreshSucceeded,
    ) -> None:
        """Log successful token refresh (INFO level).

        Args:
            event: TokenRefreshSucceeded event with provider details.
        """
        self._logger.info(
            "token_refresh_succeeded",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_id=str(event.provider_id),
            provider_name=event.provider_name,
        )

    async def handle_token_refresh_failed(
        self,
        event: TokenRefreshFailed,
    ) -> None:
        """Log failed token refresh (WARNING level).

        Args:
            event: TokenRefreshFailed event with error details.
        """
        self._logger.warning(
            "token_refresh_failed",
            event_id=str(event.event_id),
            occurred_at=event.occurred_at.isoformat(),
            user_id=str(event.user_id),
            provider_id=str(event.provider_id),
            provider_name=event.provider_name,
            error_code=event.error_code,
        )
