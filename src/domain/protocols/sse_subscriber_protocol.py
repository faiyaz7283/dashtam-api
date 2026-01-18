"""SSE Subscriber Protocol for domain layer.

This module defines the interface for subscribing to SSE event streams.
Infrastructure adapters (Redis) implement this protocol to provide
real-time event consumption for connected clients.

Architecture:
    - Protocol-based (structural typing, no inheritance)
    - Async generator for streaming events
    - Category filtering for client subscriptions
    - Last-Event-ID support for reconnection replay

Reference:
    - docs/architecture/sse-architecture.md
"""

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from src.domain.events.sse_event import SSEEvent, SSEEventCategory


class SSESubscriberProtocol(Protocol):
    """Protocol for subscribing to SSE event streams.

    Infrastructure adapters (Redis pub/sub) implement this protocol
    without inheritance. Used by the SSE endpoint to stream events
    to connected clients.

    Design:
        - Async generator for event streaming
        - Category-based filtering
        - Last-Event-ID replay for reconnection
        - Request-scoped (new instance per SSE connection)

    Example:
        >>> subscriber: SSESubscriberProtocol = get_sse_subscriber()
        >>> async for event in subscriber.subscribe(
        ...     user_id=user_id,
        ...     categories=["data_sync", "provider"],
        ... ):
        ...     yield event.to_sse_format()
    """

    async def subscribe(
        self,
        user_id: UUID,
        categories: list[str] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        """Subscribe to user's SSE event stream.

        Returns an async generator that yields SSE events as they arrive.
        Subscribes to both user-specific and broadcast channels.

        Args:
            user_id: User ID to subscribe to.
            categories: Optional list of categories to filter.
                If None, all events are yielded.
                Valid: "data_sync", "provider", "ai", "import", "portfolio", "security"

        Yields:
            SSEEvent: Events matching the subscription criteria.

        Note:
            - Runs until client disconnects or server shuts down
            - Filters by category if specified
            - Listens to both user channel and broadcast channel

        Example:
            >>> async for event in subscriber.subscribe(
            ...     user_id=user_id,
            ...     categories=["data_sync"],
            ... ):
            ...     # Only sync events for this user
            ...     yield event.to_sse_format()
        """
        ...
        # Make this a generator
        yield  # type: ignore[misc]

    async def get_missed_events(
        self,
        user_id: UUID,
        last_event_id: UUID,
        categories: list[str] | None = None,
    ) -> list[SSEEvent]:
        """Get events missed since last_event_id (reconnection replay).

        When a client reconnects with Last-Event-ID header, this method
        retrieves events that were published while the client was disconnected.

        Requires retention to be enabled (sse_enable_retention=True).

        Args:
            user_id: User ID to get events for.
            last_event_id: Last event ID received by client.
            categories: Optional category filter.

        Returns:
            List of SSEEvent objects published after last_event_id.
            Empty list if retention disabled or no events found.

        Note:
            - Returns empty list if retention is disabled
            - Events are returned in chronological order
            - Only returns events within retention window (TTL)

        Example:
            >>> missed = await subscriber.get_missed_events(
            ...     user_id=user_id,
            ...     last_event_id=UUID("01234567-..."),
            ...     categories=["data_sync"],
            ... )
            >>> for event in missed:
            ...     yield event.to_sse_format()
        """
        ...

    def filter_by_categories(
        self,
        event: SSEEvent,
        categories: list[str] | None,
    ) -> bool:
        """Check if event matches category filter.

        Helper method for filtering events by category.

        Args:
            event: Event to check.
            categories: List of category strings to match.
                If None, returns True (no filter).

        Returns:
            True if event matches filter, False otherwise.

        Example:
            >>> if subscriber.filter_by_categories(event, ["data_sync"]):
            ...     yield event.to_sse_format()
        """
        ...

    @staticmethod
    def validate_categories(categories: list[str] | None) -> list[SSEEventCategory]:
        """Validate and convert category strings to enum values.

        Args:
            categories: List of category strings from query params.

        Returns:
            List of valid SSEEventCategory enum values.

        Raises:
            ValueError: If any category string is invalid.

        Example:
            >>> valid = SSESubscriberProtocol.validate_categories(["data_sync", "ai"])
            >>> # Returns [SSEEventCategory.DATA_SYNC, SSEEventCategory.AI]
        """
        ...
