"""Event bus protocol (port) for domain events.

This module defines the EventBusProtocol interface that all event bus
implementations must satisfy. This follows the Hexagonal Architecture
pattern where the domain defines ports (interfaces) and infrastructure
provides adapters (implementations).

Architecture:
    - Protocol (structural typing, NOT ABC inheritance)
    - Domain layer defines the interface (port)
    - Infrastructure layer implements adapters (in-memory, RabbitMQ, etc.)
    - Container (src/core/container.py) provides factory function

Implementations:
    - InMemoryEventBus: src/infrastructure/events/in_memory_event_bus.py
    - RabbitMQEventBus: src/infrastructure/events/rabbitmq_event_bus.py (future)
    - KafkaEventBus: src/infrastructure/events/kafka_event_bus.py (future)

Usage:
    >>> # Application layer uses protocol (dependency injection)
    >>> from src.core.container import get_event_bus
    >>> from src.domain.events.auth_events import UserRegistered
    >>>
    >>> event_bus = get_event_bus()  # Returns EventBusProtocol implementation
    >>>
    >>> # Publish event
    >>> event = UserRegistered(user_id=uuid7(), email="test@example.com")
    >>> await event_bus.publish(event)
    >>>
    >>> # Subscribe handler
    >>> async def handle_user_registered(event: UserRegistered):
    ...     print(f"User registered: {event.email}")
    >>>
    >>> event_bus.subscribe(UserRegistered, handle_user_registered)

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 812-919)
    - docs/architecture/dependency-injection-architecture.md (Container pattern)
    - ~/starter/clean-slate-reference.md Section 9.4 (Domain Events)
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol

from src.domain.events.base_event import DomainEvent

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Type alias for event handler functions
EventHandler = Callable[[DomainEvent], Awaitable[None]]
"""Type alias for async event handler functions.

Event handlers must:
    - Accept single DomainEvent parameter (or specific event subclass)
    - Return None (side-effects only)
    - Be async (async def)
    - Handle errors gracefully (fail-open pattern)

Example:
    >>> async def log_event(event: DomainEvent) -> None:
    ...     logger.info("Event occurred", event_type=type(event).__name__)
    >>> 
    >>> async def send_email(event: UserRegistered) -> None:
    ...     await email_service.send_welcome_email(event.email)
"""


class EventBusProtocol(Protocol):
    """Protocol for event bus implementations.

    Defines the contract that all event bus adapters must implement. This is
    a structural protocol (no inheritance required) following Python 3.14+
    best practices for interface definition.

    The event bus uses the Publisher-Subscriber pattern:
        - Publishers: Domain services, command handlers, query handlers
        - Subscribers: Event handlers (logging, audit, email, session, etc.)
        - Event bus: Mediator that routes events to registered handlers

    Key Requirements:
        1. **Fail-open behavior**: One handler failure must NOT prevent other
           handlers from executing. Log errors but continue processing.
        2. **Async support**: All handlers are async to support I/O operations
           (database writes, email sending, API calls).
        3. **Type safety**: Handlers registered for specific event types only
           receive events of that type.
        4. **No ordering guarantees**: Handlers execute concurrently (use
           asyncio.gather). Do NOT assume handler execution order.

    Methods:
        subscribe: Register event handler for specific event type
        publish: Publish event to all registered handlers

    Example:
        >>> # Infrastructure implements protocol
        >>> class InMemoryEventBus:
        ...     def subscribe(self, event_type, handler):
        ...         self._handlers[event_type].append(handler)
        ...
        ...     async def publish(self, event):
        ...         handlers = self._handlers.get(type(event), [])
        ...         await asyncio.gather(
        ...             *(handler(event) for handler in handlers),
        ...             return_exceptions=True  # Fail-open
        ...         )
        >>>
        >>> # Container provides implementation
        >>> @lru_cache()
        >>> def get_event_bus() -> EventBusProtocol:
        ...     return InMemoryEventBus(logger=get_logger())

    Design Decisions:
        - **Protocol over ABC**: Structural typing (no inheritance required)
        - **Fail-open**: One handler failure doesn't break others
        - **Async handlers**: Support I/O operations (database, email, etc.)
        - **Type-based routing**: Handlers registered per event type
        - **No message queue**: In-memory for MVP (extensible to RabbitMQ/Kafka)

    Notes:
        - Event bus is application-scoped singleton (one instance per app)
        - Handlers are registered at application startup (container initialization)
        - Events are published synchronously (within same request/transaction)
        - For distributed systems, swap to RabbitMQ/Kafka adapter (no code changes)
    """

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        """Register event handler for specific event type.

        Handlers are registered at application startup (container initialization).
        Multiple handlers can subscribe to the same event type - all will be
        called when that event is published.

        Args:
            event_type: Class of event to handle (e.g., UserRegistered,
                PasswordChanged). Handler will ONLY receive events of this
                exact type (no inheritance matching).
            handler: Async function to call when event is published. Must
                accept single event parameter and return None. Handler should
                be idempotent and handle errors gracefully.

        Example:
            >>> # Register logging handler
            >>> async def log_user_registered(event: UserRegistered) -> None:
            ...     logger.info(
            ...         "user_registered",
            ...         user_id=str(event.user_id),
            ...         email=event.email,
            ...     )
            >>>
            >>> event_bus.subscribe(UserRegistered, log_user_registered)
            >>>
            >>> # Register audit handler (same event, different handler)
            >>> async def audit_user_registered(event: UserRegistered) -> None:
            ...     await audit_service.record(
            ...         action=AuditAction.USER_REGISTERED,
            ...         user_id=event.user_id,
            ...     )
            >>>
            >>> event_bus.subscribe(UserRegistered, audit_user_registered)
            >>>
            >>> # Both handlers will execute when UserRegistered is published

        Notes:
            - Handlers execute concurrently (asyncio.gather)
            - No execution order guarantees
            - Handler failures logged but don't prevent other handlers
            - Handlers should be fast (offload heavy work to queues)
        """
        ...

    async def publish(
        self,
        event: DomainEvent,
        session: "AsyncSession | None" = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Publish event to all registered handlers.

        Executes all handlers registered for the event's type concurrently.
        Uses fail-open behavior: if one handler fails, others still execute.
        Handler exceptions are logged but NOT propagated to publisher.

        Args:
            event: Domain event to publish (subclass of DomainEvent). All
                handlers registered for type(event) will be called with this
                event instance.
            session: Optional database session for handlers that need database
                access (e.g., AuditEventHandler). If provided, handlers can use
                this session instead of creating their own. This ensures proper
                session lifecycle management and prevents "Event loop is closed"
                errors in tests. Defaults to None for backward compatibility.
            metadata: Optional request metadata (IP address, user agent) for
                audit trail enrichment (PCI-DSS 10.2.7). Event handlers can
                access this via event_bus.get_metadata(). Defaults to None.

        Example:
            >>> # In command handler (after successful business logic)
            >>> user = User(email="test@example.com", ...)
            >>> await user_repo.save(user)
            >>> await session.commit()  # ← Commit BEFORE publishing
            >>>
            >>> # Publish event (all registered handlers execute)
            >>> event = UserRegistered(user_id=user.id, email=user.email)
            >>> await event_bus.publish(event)  # ← Fire and forget
            >>>
            >>> # If audit handler fails, logging/email handlers still execute
            >>> # If NO handlers registered, publish is no-op (no error)

        Flow:
            1. Look up handlers registered for type(event)
            2. Execute all handlers concurrently (asyncio.gather)
            3. Log any handler exceptions (fail-open)
            4. Return (never raise exceptions to publisher)

        Performance:
            - Handlers execute concurrently (not sequentially)
            - Average overhead: <10ms for 4 handlers (in-memory)
            - For distributed systems, consider async message queue

        Notes:
            - ALWAYS publish events AFTER commit (facts, not intents)
            - Exception: ATTEMPT events (publish BEFORE operation)
            - No handlers = no-op (not an error)
            - Handler failures logged with event_id for debugging
        """
        ...
