"""SSE Publisher Protocol for domain layer.

This module defines the interface for publishing SSE events to connected clients.
Infrastructure adapters (Redis) implement this protocol to provide real-time
event distribution.

Architecture:
    - Protocol-based (structural typing, no inheritance)
    - Async operations for non-blocking pub/sub
    - Fail-open design (SSE failures don't break core API)
    - No framework dependencies in domain layer

Reference:
    - docs/architecture/sse-architecture.md
"""

from typing import Protocol
from uuid import UUID

from src.domain.events.sse_event import SSEEvent


class SSEPublisherProtocol(Protocol):
    """Protocol for publishing SSE events to connected clients.

    Infrastructure adapters (Redis pub/sub) implement this protocol
    without inheritance. Used by SSEEventHandler to publish events
    when domain events occur.

    Design:
        - Async operations for non-blocking I/O
        - Fail-open: publish failures logged but don't raise
        - Optional retention for Last-Event-ID replay

    Example:
        >>> publisher: SSEPublisherProtocol = get_sse_publisher()
        >>> event = SSEEvent(
        ...     event_type=SSEEventType.SYNC_ACCOUNTS_COMPLETED,
        ...     user_id=user_id,
        ...     data={"account_count": 3},
        ... )
        >>> await publisher.publish(event)
    """

    async def publish(self, event: SSEEvent) -> None:
        """Publish SSE event to user's channel.

        Routes event to the user's Redis pub/sub channel. If retention
        is enabled, also stores in Redis Stream for replay.

        Args:
            event: SSE event to publish. Contains user_id for routing.

        Note:
            - Fail-open: Errors are logged but not raised
            - Non-blocking: Returns immediately after publish
            - User_id extracted from event for channel routing

        Example:
            >>> await publisher.publish(SSEEvent(
            ...     event_type=SSEEventType.PROVIDER_TOKEN_EXPIRING,
            ...     user_id=user_id,
            ...     data={"connection_id": str(conn_id), "expires_in": 3600},
            ... ))
        """
        ...

    async def publish_to_user(self, user_id: UUID, event: SSEEvent) -> None:
        """Publish SSE event to specific user's channel.

        Alternative to publish() when event needs to be sent to a different
        user than the one in the event (e.g., security notifications to
        all user sessions).

        Args:
            user_id: Target user ID.
            event: SSE event to publish.

        Note:
            Same fail-open behavior as publish().
        """
        ...

    async def broadcast(self, event: SSEEvent) -> None:
        """Broadcast SSE event to all connected clients.

        Publishes to a global broadcast channel that all SSE subscribers
        listen to. Use sparingly - most events should be user-specific.

        Args:
            event: SSE event to broadcast.

        Use cases:
            - System-wide maintenance notifications
            - Feature announcements

        Note:
            Event's user_id is preserved but event goes to all users.
        """
        ...
