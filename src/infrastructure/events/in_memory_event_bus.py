"""In-memory event bus implementation.

This module implements the EventBusProtocol using an in-memory dictionary-based
registry. Suitable for MVP and single-server deployments. For distributed
systems or high-volume production, swap to RabbitMQ/Kafka adapter.

Architecture:
    - Implements EventBusProtocol (hexagonal adapter pattern)
    - Dictionary-based handler registry (event_type → list of handlers)
    - Fail-open behavior (one handler failure doesn't break others)
    - Concurrent handler execution (asyncio.gather)
    - Comprehensive error logging for handler failures

Usage:
    >>> # Container creates singleton instance
    >>> @lru_cache()
    >>> def get_event_bus() -> EventBusProtocol:
    ...     return InMemoryEventBus(logger=get_logger())
    >>>
    >>> # Application layer uses protocol
    >>> event_bus = get_event_bus()
    >>> event_bus.subscribe(UserRegistered, log_user_registered)
    >>> await event_bus.publish(UserRegistered(user_id=uuid4(), email="test"))

Reference:
    - docs/architecture/domain-events-architecture.md (Lines 920-1067)
    - docs/architecture/dependency-injection-architecture.md (Container pattern)
"""

import asyncio
from collections import defaultdict

from src.domain.events.base_event import DomainEvent
from src.domain.protocols.event_bus_protocol import EventHandler
from src.domain.protocols.logger_protocol import LoggerProtocol


class InMemoryEventBus:
    """In-memory event bus with fail-open behavior.

    Implements EventBusProtocol using dictionary-based handler registry.
    Executes handlers concurrently with asyncio.gather and fail-open error
    handling (one handler failure doesn't prevent other handlers from executing).

    Thread Safety:
        - NOT thread-safe (single-server, single-threaded async design)
        - For multi-threaded, use locks or separate adapter
        - For distributed systems, use RabbitMQ/Kafka adapter

    Performance:
        - O(1) handler lookup by event type
        - Concurrent handler execution (asyncio.gather)
        - Average overhead: <10ms for 4 handlers

    Attributes:
        _handlers: Dictionary mapping event types to list of async handlers.
            Key: Event class (e.g., UserRegistered)
            Value: List of async handler functions
        _logger: Logger for handler failures and event publishing

    Example:
        >>> # Subscribe handlers
        >>> bus = InMemoryEventBus(logger=logger)
        >>> bus.subscribe(UserRegistered, log_user_registered)
        >>> bus.subscribe(UserRegistered, audit_user_registered)
        >>> bus.subscribe(UserRegistered, send_welcome_email)
        >>>
        >>> # Publish event (all 3 handlers execute concurrently)
        >>> event = UserRegistered(user_id=uuid4(), email="test@example.com")
        >>> await bus.publish(event)
        >>>
        >>> # If audit handler fails, logging and email handlers still execute

    Design Decisions:
        - **Fail-open**: Handler failures logged but not propagated
        - **Concurrent**: asyncio.gather for parallel handler execution
        - **No ordering**: Handlers execute concurrently (order undefined)
        - **In-memory**: Simple dictionary (no persistence, no distribution)
    """

    def __init__(self, logger: LoggerProtocol) -> None:
        """Initialize event bus with logger.

        Args:
            logger: Logger for handler failures and event publishing. Used to
                log handler exceptions (warning level) and event publishing
                (debug level for non-ATTEMPT events).

        Example:
            >>> from src.core.container import get_logger
            >>> logger = get_logger()
            >>> bus = InMemoryEventBus(logger=logger)
        """
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)
        self._logger = logger

    def subscribe(
        self,
        event_type: type[DomainEvent],
        handler: EventHandler,
    ) -> None:
        """Register event handler for specific event type.

        Handlers registered for the same event type will ALL be called when
        that event is published. Handlers execute concurrently (no ordering).

        Args:
            event_type: Class of event to handle (e.g., UserRegistered).
                Only exact type matches (no inheritance matching).
            handler: Async function to call when event is published. Must
                accept single event parameter and return None.

        Example:
            >>> async def log_event(event: UserRegistered) -> None:
            ...     logger.info("User registered", user_id=str(event.user_id))
            >>>
            >>> bus.subscribe(UserRegistered, log_event)
            >>>
            >>> # Multiple handlers for same event
            >>> bus.subscribe(UserRegistered, audit_event)
            >>> bus.subscribe(UserRegistered, send_email)

        Notes:
            - Handlers execute concurrently (asyncio.gather)
            - No duplicate detection (same handler can be registered twice)
            - Handlers should be idempotent (may be called multiple times)
        """
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        """Publish event to all registered handlers.

        Executes all handlers concurrently with fail-open behavior. Handler
        exceptions are logged but NOT propagated to publisher. If no handlers
        are registered, this is a no-op (not an error).

        Args:
            event: Domain event to publish (subclass of DomainEvent). All
                handlers registered for type(event) will be called.

        Example:
            >>> # After successful business logic
            >>> user = User(email="test@example.com", ...)
            >>> await user_repo.save(user)
            >>> await session.commit()  # ← COMMIT FIRST
            >>>
            >>> # Publish event (all handlers execute)
            >>> event = UserRegistered(user_id=user.id, email=user.email)
            >>> await bus.publish(event)
            >>>
            >>> # If audit handler fails:
            >>> # - Audit failure logged (warning level)
            >>> # - Logging/email handlers still execute
            >>> # - No exception raised to publisher

        Flow:
            1. Look up handlers for type(event)
            2. If no handlers, return immediately (no-op)
            3. Execute all handlers with asyncio.gather(return_exceptions=True)
            4. Log any handler exceptions (warning level)
            5. Return (never raise exceptions)

        Performance:
            - Handler lookup: O(1)
            - Handler execution: Concurrent (not sequential)
            - Average latency: <10ms for 4 handlers (in-memory)

        Notes:
            - No handlers = no-op (not an error)
            - Handler failures logged with event_id for debugging
            - NEVER raises exceptions (fail-open guarantee)
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            # No handlers registered (not an error for optional workflows)
            return

        # Log event publishing (debug level) - helpful for debugging
        self._logger.debug(
            "event_publishing",
            event_type=event_type.__name__,
            event_id=str(event.event_id),
            handler_count=len(handlers),
        )

        # Execute all handlers concurrently with fail-open behavior
        # return_exceptions=True prevents one handler failure from breaking others
        results = await asyncio.gather(
            *(handler(event) for handler in handlers),
            return_exceptions=True,  # ← Fail-open: catch exceptions
        )

        # Log any handler failures (warning level)
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                handler_name = handlers[idx].__name__
                self._logger.warning(
                    "event_handler_failed",
                    event_type=event_type.__name__,
                    event_id=str(event.event_id),
                    handler_name=handler_name,
                    error_type=type(result).__name__,
                    error_message=str(result),
                    # Include stack trace for debugging
                    exc_info=result,
                )
