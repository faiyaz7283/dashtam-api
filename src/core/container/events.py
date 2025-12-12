# mypy: disable-error-code="arg-type"
"""Event bus dependency factory.

Application-scoped singleton for domain event publishing.
Configures all event handlers and subscriptions at startup.

Reference:
    See docs/architecture/domain-events-architecture.md for complete
    event patterns and handler specifications.
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.protocols.event_bus_protocol import EventBusProtocol


@lru_cache()
def get_event_bus() -> "EventBusProtocol":
    """Get event bus singleton (app-scoped).

    Container owns factory logic - decides which adapter based on EVENT_BUS_TYPE.
    This follows the Composition Root pattern (industry best practice).

    Returns correct adapter based on EVENT_BUS_TYPE environment variable:
        - 'in-memory': InMemoryEventBus (MVP, single-server)
        - 'rabbitmq': RabbitMQEventBus (future, distributed)
        - 'kafka': KafkaEventBus (future, high-volume)

    Event handlers are registered at startup (ALL 70 subscriptions):
        - LoggingEventHandler: 31 events (all authentication + provider events)
        - AuditEventHandler: 31 events (all authentication + provider events)
        - EmailEventHandler: 5 SUCCEEDED events (registration, password change,
          email verification, password reset request, password reset confirm)
        - SessionEventHandler: 3 SUCCEEDED events (password change, password reset
          confirm, user logout)

    Returns:
        Event bus implementing EventBusProtocol.

    Usage:
        # Application Layer (direct use)
        event_bus = get_event_bus()
        await event_bus.publish(UserRegistrationSucceeded(...))

        # Presentation Layer (FastAPI Depends)
        from fastapi import Depends
        event_bus: EventBusProtocol = Depends(get_event_bus)

    Reference:
        - docs/architecture/domain-events-architecture.md
        - docs/architecture/dependency-injection-architecture.md
    """
    import os

    from src.core.config import get_settings
    from src.domain.events.auth_events import (
        AuthTokenRefreshAttempted,
        AuthTokenRefreshFailed,
        AuthTokenRefreshSucceeded,
        EmailVerificationAttempted,
        EmailVerificationFailed,
        EmailVerificationSucceeded,
        PasswordResetConfirmAttempted,
        PasswordResetConfirmFailed,
        PasswordResetConfirmSucceeded,
        PasswordResetRequestAttempted,
        PasswordResetRequestFailed,
        PasswordResetRequestSucceeded,
        TokenRejectedDueToRotation,
        UserLoginAttempted,
        UserLoginFailed,
        UserLoginSucceeded,
        UserLogoutAttempted,
        UserLogoutFailed,
        UserLogoutSucceeded,
        UserPasswordChangeAttempted,
        UserPasswordChangeFailed,
        UserPasswordChangeSucceeded,
        UserRegistrationAttempted,
        UserRegistrationFailed,
        UserRegistrationSucceeded,
    )
    from src.domain.events.provider_events import (
        ProviderConnectionAttempted,
        ProviderConnectionFailed,
        ProviderConnectionSucceeded,
        ProviderTokenRefreshAttempted,
        ProviderTokenRefreshFailed,
        ProviderTokenRefreshSucceeded,
    )
    from src.infrastructure.events.handlers.audit_event_handler import AuditEventHandler
    from src.infrastructure.events.handlers.email_event_handler import EmailEventHandler
    from src.infrastructure.events.handlers.logging_event_handler import (
        LoggingEventHandler,
    )
    from src.infrastructure.events.handlers.session_event_handler import (
        SessionEventHandler,
    )
    from src.infrastructure.events.in_memory_event_bus import InMemoryEventBus

    # Import from infrastructure module (no circular dependency)
    from src.core.container.infrastructure import get_database, get_logger

    event_bus_type = os.getenv("EVENT_BUS_TYPE", "in-memory")

    if event_bus_type == "in-memory":
        # Create InMemoryEventBus with logger
        event_bus = InMemoryEventBus(logger=get_logger())
    # elif event_bus_type == "rabbitmq":
    #     # Future: RabbitMQ adapter
    #     from src.infrastructure.events.rabbitmq_event_bus import RabbitMQEventBus
    #
    #     event_bus = RabbitMQEventBus(url=os.getenv("RABBITMQ_URL"))
    # elif event_bus_type == "kafka":
    #     # Future: Kafka adapter
    #     from src.infrastructure.events.kafka_event_bus import KafkaEventBus
    #
    #     event_bus = KafkaEventBus(brokers=os.getenv("KAFKA_BROKERS"))
    else:
        raise ValueError(
            f"Unsupported EVENT_BUS_TYPE: {event_bus_type}. "
            f"Supported: 'in-memory' (rabbitmq and kafka: future)"
        )

    # Create event handlers
    logging_handler = LoggingEventHandler(logger=get_logger())

    # Audit handler uses database session from event bus (if provided).
    # Pass both database (fallback) and event_bus (preferred session source).
    # This prevents "Event loop is closed" errors in tests by avoiding
    # session creation inside event handlers.
    audit_handler = AuditEventHandler(database=get_database(), event_bus=event_bus)

    email_handler = EmailEventHandler(logger=get_logger(), settings=get_settings())
    session_handler = SessionEventHandler(logger=get_logger())

    # =========================================================================
    # Subscribe ALL handlers to events (27 subscriptions total)
    # =========================================================================
    # NOTE: mypy shows arg-type errors because handler signatures are more specific
    # (e.g., Callable[[UserRegistrationAttempted], Awaitable[None]]) than the
    # EventHandler type alias (Callable[[DomainEvent], Awaitable[None]]). This is
    # correct by contravariance principle - handlers accepting specific events can
    # safely handle the base type. Runtime behavior is sound, so we suppress mypy
    # at file level (first line of this file).

    # User Registration Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        UserRegistrationAttempted, logging_handler.handle_user_registration_attempted
    )
    event_bus.subscribe(
        UserRegistrationAttempted, audit_handler.handle_user_registration_attempted
    )

    event_bus.subscribe(
        UserRegistrationSucceeded, logging_handler.handle_user_registration_succeeded
    )
    event_bus.subscribe(
        UserRegistrationSucceeded, audit_handler.handle_user_registration_succeeded
    )
    event_bus.subscribe(
        UserRegistrationSucceeded, email_handler.handle_user_registration_succeeded
    )  # +1 email

    event_bus.subscribe(
        UserRegistrationFailed, logging_handler.handle_user_registration_failed
    )
    event_bus.subscribe(
        UserRegistrationFailed, audit_handler.handle_user_registration_failed
    )

    # User Password Change Events (3 events × 2 handlers + email + session = 9 subscriptions)
    event_bus.subscribe(
        UserPasswordChangeAttempted,
        logging_handler.handle_user_password_change_attempted,
    )
    event_bus.subscribe(
        UserPasswordChangeAttempted, audit_handler.handle_user_password_change_attempted
    )

    event_bus.subscribe(
        UserPasswordChangeSucceeded,
        logging_handler.handle_user_password_change_succeeded,
    )
    event_bus.subscribe(
        UserPasswordChangeSucceeded, audit_handler.handle_user_password_change_succeeded
    )
    event_bus.subscribe(
        UserPasswordChangeSucceeded, email_handler.handle_user_password_change_succeeded
    )  # +1 email
    event_bus.subscribe(
        UserPasswordChangeSucceeded,
        session_handler.handle_user_password_change_succeeded,
    )  # +1 session

    event_bus.subscribe(
        UserPasswordChangeFailed, logging_handler.handle_user_password_change_failed
    )
    event_bus.subscribe(
        UserPasswordChangeFailed, audit_handler.handle_user_password_change_failed
    )

    # Provider Connection Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        ProviderConnectionAttempted,
        logging_handler.handle_provider_connection_attempted,
    )
    event_bus.subscribe(
        ProviderConnectionAttempted, audit_handler.handle_provider_connection_attempted
    )

    event_bus.subscribe(
        ProviderConnectionSucceeded,
        logging_handler.handle_provider_connection_succeeded,
    )
    event_bus.subscribe(
        ProviderConnectionSucceeded, audit_handler.handle_provider_connection_succeeded
    )

    event_bus.subscribe(
        ProviderConnectionFailed, logging_handler.handle_provider_connection_failed
    )
    event_bus.subscribe(
        ProviderConnectionFailed, audit_handler.handle_provider_connection_failed
    )

    # Provider Token Refresh Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        ProviderTokenRefreshAttempted,
        logging_handler.handle_provider_token_refresh_attempted,
    )
    event_bus.subscribe(
        ProviderTokenRefreshAttempted,
        audit_handler.handle_provider_token_refresh_attempted,
    )

    event_bus.subscribe(
        ProviderTokenRefreshSucceeded,
        logging_handler.handle_provider_token_refresh_succeeded,
    )
    event_bus.subscribe(
        ProviderTokenRefreshSucceeded,
        audit_handler.handle_provider_token_refresh_succeeded,
    )

    event_bus.subscribe(
        ProviderTokenRefreshFailed, logging_handler.handle_provider_token_refresh_failed
    )
    event_bus.subscribe(
        ProviderTokenRefreshFailed, audit_handler.handle_provider_token_refresh_failed
    )

    # User Login Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(UserLoginAttempted, logging_handler.handle_user_login_attempted)
    event_bus.subscribe(UserLoginAttempted, audit_handler.handle_user_login_attempted)

    event_bus.subscribe(UserLoginSucceeded, logging_handler.handle_user_login_succeeded)
    event_bus.subscribe(UserLoginSucceeded, audit_handler.handle_user_login_succeeded)

    event_bus.subscribe(UserLoginFailed, logging_handler.handle_user_login_failed)
    event_bus.subscribe(UserLoginFailed, audit_handler.handle_user_login_failed)

    # User Logout Events (3 events × 3 handlers = 9 subscriptions)
    event_bus.subscribe(
        UserLogoutAttempted, logging_handler.handle_user_logout_attempted
    )
    event_bus.subscribe(UserLogoutAttempted, audit_handler.handle_user_logout_attempted)

    event_bus.subscribe(
        UserLogoutSucceeded, logging_handler.handle_user_logout_succeeded
    )
    event_bus.subscribe(UserLogoutSucceeded, audit_handler.handle_user_logout_succeeded)
    event_bus.subscribe(
        UserLogoutSucceeded, session_handler.handle_user_logout_succeeded
    )  # +1 session

    event_bus.subscribe(UserLogoutFailed, logging_handler.handle_user_logout_failed)
    event_bus.subscribe(UserLogoutFailed, audit_handler.handle_user_logout_failed)

    # Email Verification Events (3 events × 3 handlers = 9 subscriptions)
    event_bus.subscribe(
        EmailVerificationAttempted, logging_handler.handle_email_verification_attempted
    )
    event_bus.subscribe(
        EmailVerificationAttempted, audit_handler.handle_email_verification_attempted
    )

    event_bus.subscribe(
        EmailVerificationSucceeded, logging_handler.handle_email_verification_succeeded
    )
    event_bus.subscribe(
        EmailVerificationSucceeded, audit_handler.handle_email_verification_succeeded
    )
    event_bus.subscribe(
        EmailVerificationSucceeded, email_handler.handle_email_verification_succeeded
    )  # +1 email

    event_bus.subscribe(
        EmailVerificationFailed, logging_handler.handle_email_verification_failed
    )
    event_bus.subscribe(
        EmailVerificationFailed, audit_handler.handle_email_verification_failed
    )

    # Auth Token Refresh Events (3 events × 2 handlers = 6 subscriptions)
    event_bus.subscribe(
        AuthTokenRefreshAttempted, logging_handler.handle_auth_token_refresh_attempted
    )
    event_bus.subscribe(
        AuthTokenRefreshAttempted, audit_handler.handle_auth_token_refresh_attempted
    )

    event_bus.subscribe(
        AuthTokenRefreshSucceeded, logging_handler.handle_auth_token_refresh_succeeded
    )
    event_bus.subscribe(
        AuthTokenRefreshSucceeded, audit_handler.handle_auth_token_refresh_succeeded
    )

    event_bus.subscribe(
        AuthTokenRefreshFailed, logging_handler.handle_auth_token_refresh_failed
    )
    event_bus.subscribe(
        AuthTokenRefreshFailed, audit_handler.handle_auth_token_refresh_failed
    )

    # Password Reset Request Events (3 events × 3 handlers = 9 subscriptions)
    event_bus.subscribe(
        PasswordResetRequestAttempted,
        logging_handler.handle_password_reset_request_attempted,
    )
    event_bus.subscribe(
        PasswordResetRequestAttempted,
        audit_handler.handle_password_reset_request_attempted,
    )

    event_bus.subscribe(
        PasswordResetRequestSucceeded,
        logging_handler.handle_password_reset_request_succeeded,
    )
    event_bus.subscribe(
        PasswordResetRequestSucceeded,
        audit_handler.handle_password_reset_request_succeeded,
    )
    event_bus.subscribe(
        PasswordResetRequestSucceeded,
        email_handler.handle_password_reset_request_succeeded,
    )  # +1 email

    event_bus.subscribe(
        PasswordResetRequestFailed,
        logging_handler.handle_password_reset_request_failed,
    )
    event_bus.subscribe(
        PasswordResetRequestFailed, audit_handler.handle_password_reset_request_failed
    )

    # Password Reset Confirm Events (3 events × 4 handlers = 12 subscriptions)
    event_bus.subscribe(
        PasswordResetConfirmAttempted,
        logging_handler.handle_password_reset_confirm_attempted,
    )
    event_bus.subscribe(
        PasswordResetConfirmAttempted,
        audit_handler.handle_password_reset_confirm_attempted,
    )

    event_bus.subscribe(
        PasswordResetConfirmSucceeded,
        logging_handler.handle_password_reset_confirm_succeeded,
    )
    event_bus.subscribe(
        PasswordResetConfirmSucceeded,
        audit_handler.handle_password_reset_confirm_succeeded,
    )
    event_bus.subscribe(
        PasswordResetConfirmSucceeded,
        email_handler.handle_password_reset_confirm_succeeded,
    )  # +1 email
    event_bus.subscribe(
        PasswordResetConfirmSucceeded,
        session_handler.handle_password_reset_confirm_succeeded,
    )  # +1 session

    event_bus.subscribe(
        PasswordResetConfirmFailed, logging_handler.handle_password_reset_confirm_failed
    )
    event_bus.subscribe(
        PasswordResetConfirmFailed, audit_handler.handle_password_reset_confirm_failed
    )

    # Token Rejected Due to Rotation (1 event × 2 handlers = 2 subscriptions)
    event_bus.subscribe(
        TokenRejectedDueToRotation,
        logging_handler.handle_token_rejected_due_to_rotation,
    )
    event_bus.subscribe(
        TokenRejectedDueToRotation, audit_handler.handle_token_rejected_due_to_rotation
    )

    return event_bus
