"""SSE Event Handler - bridges domain events to SSE streams.

This handler subscribes to domain events (via event bus) and publishes
corresponding SSE events to connected clients via Redis pub/sub.

Architecture:
    - App-scoped singleton (same pattern as LoggingEventHandler)
    - Subscribed at container startup (not request-scoped)
    - Uses registry-driven mappings (DOMAIN_TO_SSE_MAPPING)
    - Fail-open design: errors logged but don't propagate

Lifecycle:
    1. Container creates singleton SSEEventHandler at startup
    2. Container subscribes handler.handle to domain events with SSE mappings
    3. When domain event published → handler transforms → publisher sends to Redis
    4. SSE endpoint subscribers receive events from Redis pub/sub

Reference:
    - docs/architecture/sse-architecture.md (Section 6)
"""

import logging
from typing import Any

from src.domain.events.base_event import DomainEvent
from src.domain.events.sse_event import SSEEvent
from src.domain.events.sse_registry import (
    DomainToSSEMapping,
    get_domain_event_to_sse_mapping,
)
from src.domain.protocols.sse_publisher_protocol import SSEPublisherProtocol


class SSEEventHandler:
    """Event handler that bridges domain events to SSE streams.

    Subscribes to domain events and transforms them into SSE events
    for real-time client notification.

    Note:
        - App-scoped singleton (NOT request-scoped)
        - Same pattern as LoggingEventHandler, AuditEventHandler
        - Does NOT use handler_factory (that's for CQRS handlers)

    Attributes:
        _publisher: SSE publisher for sending events to Redis.
        _logger: Logger instance.
        _mapping: Cached domain-to-SSE mapping from registry.

    Example:
        >>> # Container wires at startup
        >>> publisher = get_sse_publisher()
        >>> handler = SSEEventHandler(publisher=publisher)
        >>>
        >>> # Subscribe to domain events with SSE mappings
        >>> for domain_event_class in get_domain_event_to_sse_mapping():
        ...     event_bus.subscribe(domain_event_class, handler.handle)
    """

    def __init__(
        self,
        publisher: SSEPublisherProtocol,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize SSE event handler.

        Args:
            publisher: SSE publisher for sending events to Redis.
            logger: Optional logger (creates default if not provided).
        """
        self._publisher = publisher
        self._logger = logger or logging.getLogger(__name__)
        self._mapping = get_domain_event_to_sse_mapping()

    async def handle(self, event: DomainEvent) -> None:
        """Handle domain event and publish corresponding SSE event.

        This is the generic handler method that can be subscribed to
        any domain event. It looks up the mapping and transforms
        the event appropriately.

        Args:
            event: Domain event to process.

        Note:
            - Fail-open: errors logged but not raised
            - Silently ignores events without SSE mapping
        """
        event_class = type(event)

        # Look up mapping for this event type
        mapping = self._mapping.get(event_class)
        if mapping is None:
            # No SSE mapping for this event - this is fine
            # Not all domain events need SSE notifications
            return

        try:
            # Transform domain event to SSE event
            sse_event = self._transform_event(event, mapping)

            # Publish SSE event
            await self._publisher.publish(sse_event)

            self._logger.debug(
                "Published SSE event from domain event",
                extra={
                    "domain_event": event_class.__name__,
                    "sse_event_type": sse_event.event_type.value,
                    "user_id": str(sse_event.user_id),
                    "event_id": str(sse_event.event_id),
                },
            )

        except Exception as e:
            # Fail-open: log error but don't propagate
            # SSE is non-critical - core functionality must continue
            self._logger.error(
                "Failed to publish SSE event from domain event (fail-open)",
                extra={
                    "domain_event": event_class.__name__,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    def _transform_event(
        self,
        domain_event: DomainEvent,
        mapping: DomainToSSEMapping,
    ) -> SSEEvent:
        """Transform domain event to SSE event using mapping.

        Args:
            domain_event: Domain event to transform.
            mapping: Mapping with extractors for payload and user_id.

        Returns:
            SSEEvent ready for publishing.

        Raises:
            Exception: If extractors fail (caught by caller).
        """
        # Extract user_id from domain event
        user_id = mapping.user_id_extractor(domain_event)

        # Extract payload from domain event
        payload: dict[str, Any] = mapping.payload_extractor(domain_event)

        return SSEEvent(
            event_type=mapping.sse_event_type,
            user_id=user_id,
            data=payload,
        )

    def has_mapping_for(self, event_class: type[DomainEvent]) -> bool:
        """Check if handler has mapping for event class.

        Useful for testing and debugging.

        Args:
            event_class: Domain event class to check.

        Returns:
            True if mapping exists, False otherwise.
        """
        return event_class in self._mapping

    def get_mapped_event_types(self) -> list[type[DomainEvent]]:
        """Get list of domain event types with SSE mappings.

        Returns:
            List of domain event classes that have SSE mappings.
        """
        return list(self._mapping.keys())
