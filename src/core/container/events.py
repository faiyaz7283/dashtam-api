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

    Event handlers are registered at startup (ALL 27 subscriptions):
        - LoggingEventHandler: 12 events (all authentication events)
        - AuditEventHandler: 12 events (all authentication events)
        - EmailEventHandler: 2 SUCCEEDED events (registration, password change)
        - SessionEventHandler: 1 SUCCEEDED event (password change)

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

    return event_bus
