# mypy: disable-error-code="arg-type"
"""Event bus dependency factory.

Application-scoped singleton for domain event publishing.
Configures all event handlers and subscriptions at startup using
registry-driven auto-wiring (F7.7: Domain Events Compliance Audit).

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

    Event handlers are AUTOMATICALLY registered at startup using EVENT_REGISTRY
    (F7.7: Registry-driven auto-wiring). The registry defines ALL event metadata
    (category, workflow, phase, handler requirements) and this factory:
        1. Loops through EVENT_REGISTRY
        2. Dynamically computes handler method names from workflow_name + phase
        3. Subscribes handlers based on metadata.requires_* flags

    Current Registry Status (56 events across 7 categories):
        - Authentication (28): 7 workflows × 3-state + 1 operational
        - Authorization (6): 2 workflows × 3-state
        - Provider (9): 3 workflows × 3-state
        - Data Sync (0): Placeholders for 4 workflows × 3-state (Phase 2)
        - Session (10): Metadata enrichment events
        - Rate Limit (3): Rate limit enforcement events
        - Admin (0): Future administrative events

    Benefits of registry-driven approach:
        - Single source of truth (registry.py)
        - Self-validating (tests fail if handlers/audit actions missing)
        - Automatic wiring (adding event = add to registry, tests enforce rest)
        - No drift (manual code eliminated)

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
    from src.domain.events.registry import EVENT_REGISTRY

    # Load settings from centralized config (single source of truth)
    settings = get_settings()

    # Strict mode: Fail-fast if handler methods missing (production safety)
    # Graceful mode: Skip missing handlers, continue (development flexibility)
    # Default: false (graceful) until F7.7 Phase 2-8 complete, then switch to true
    EVENTS_STRICT_MODE = settings.events_strict_mode
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
    # REGISTRY-DRIVEN AUTO-WIRING (F7.7: Domain Events Compliance Audit)
    # =========================================================================
    # Instead of manually subscribing ~100 handlers to events, we use the
    # EVENT_REGISTRY as the single source of truth. This eliminates ~500 lines
    # of manual subscription code and prevents drift.
    #
    # For each event in EVENT_REGISTRY:
    #   1. Compute handler method name: handle_{workflow_name}_{phase}
    #   2. Subscribe handlers based on metadata.requires_* flags
    #
    # Benefits:
    #   - Adding new event: Just add to registry, tests enforce rest
    #   - No manual subscription management
    #   - Can't drift (tests fail if handler methods missing)
    #
    # NOTE: mypy shows arg-type errors because handler signatures are more specific
    # (e.g., Callable[[UserRegistrationAttempted], Awaitable[None]]) than the
    # EventHandler type alias (Callable[[DomainEvent], Awaitable[None]]). This is
    # correct by contravariance principle - handlers accepting specific events can
    # safely handle the base type. Runtime behavior is sound, so we suppress mypy
    # at file level (first line of this file).
    # =========================================================================

    logger = get_logger()

    for metadata in EVENT_REGISTRY:
        event_class = metadata.event_class

        # Compute handler method name from workflow_name + phase
        # E.g., "user_registration" + "attempted" = "handle_user_registration_attempted"
        method_name = f"handle_{metadata.workflow_name}_{metadata.phase.value}"

        # Subscribe handlers based on metadata requirements
        # Mode-dependent behavior:
        #   - STRICT (production): Crash if required handler missing
        #   - GRACEFUL (development): Skip missing handlers, log warning
        if metadata.requires_logging:
            handler_method = getattr(logging_handler, method_name, None)
            if not handler_method:
                if EVENTS_STRICT_MODE:
                    raise RuntimeError(
                        f"EVENTS_STRICT_MODE: Missing required logging handler\n"
                        f"Event: {event_class.__name__}\n"
                        f"Expected method: LoggingEventHandler.{method_name}\n\n"
                        f"Fix: Implement handler in src/infrastructure/events/handlers/logging_event_handler.py\n"
                        f"Or disable strict mode: Set EVENTS_STRICT_MODE=false in .env"
                    )
                logger.warning(
                    "Missing logging handler (graceful mode)",
                    event_class=event_class.__name__,
                    handler_method=method_name,
                )
            else:
                event_bus.subscribe(event_class, handler_method)

        if metadata.requires_audit:
            handler_method = getattr(audit_handler, method_name, None)
            if not handler_method:
                if EVENTS_STRICT_MODE:
                    raise RuntimeError(
                        f"EVENTS_STRICT_MODE: Missing required audit handler (COMPLIANCE CRITICAL)\n"
                        f"Event: {event_class.__name__}\n"
                        f"Expected method: AuditEventHandler.{method_name}\n\n"
                        f"Audit handlers are REQUIRED for PCI-DSS/SOC 2 compliance.\n"
                        f"Fix: Implement handler in src/infrastructure/events/handlers/audit_event_handler.py\n"
                        f"Or disable strict mode: Set EVENTS_STRICT_MODE=false in .env"
                    )
                logger.warning(
                    "Missing audit handler (graceful mode - COMPLIANCE RISK)",
                    event_class=event_class.__name__,
                    handler_method=method_name,
                )
            else:
                event_bus.subscribe(event_class, handler_method)

        if metadata.requires_email:
            handler_method = getattr(email_handler, method_name, None)
            if not handler_method:
                if EVENTS_STRICT_MODE:
                    raise RuntimeError(
                        f"EVENTS_STRICT_MODE: Missing required email handler\n"
                        f"Event: {event_class.__name__}\n"
                        f"Expected method: EmailEventHandler.{method_name}\n\n"
                        f"Fix: Implement handler in src/infrastructure/events/handlers/email_event_handler.py\n"
                        f"Or disable strict mode: Set EVENTS_STRICT_MODE=false in .env"
                    )
                logger.warning(
                    "Missing email handler (graceful mode)",
                    event_class=event_class.__name__,
                    handler_method=method_name,
                )
            else:
                event_bus.subscribe(event_class, handler_method)

        if metadata.requires_session:
            handler_method = getattr(session_handler, method_name, None)
            if not handler_method:
                if EVENTS_STRICT_MODE:
                    raise RuntimeError(
                        f"EVENTS_STRICT_MODE: Missing required session handler\n"
                        f"Event: {event_class.__name__}\n"
                        f"Expected method: SessionEventHandler.{method_name}\n\n"
                        f"Fix: Implement handler in src/infrastructure/events/handlers/session_event_handler.py\n"
                        f"Or disable strict mode: Set EVENTS_STRICT_MODE=false in .env"
                    )
                logger.warning(
                    "Missing session handler (graceful mode)",
                    event_class=event_class.__name__,
                    handler_method=method_name,
                )
            else:
                event_bus.subscribe(event_class, handler_method)

    return event_bus
