"""Redis SSE Publisher implementing SSEPublisherProtocol.

This adapter publishes SSE events via Redis pub/sub for real-time delivery
to connected clients. Optionally stores events in Redis Streams for
Last-Event-ID replay on reconnection.

Architecture:
    - Implements SSEPublisherProtocol without inheritance (structural typing)
    - Uses Redis pub/sub for horizontal scaling (multiple API instances)
    - Optional Redis Streams for event retention
    - Fail-open design: publish errors are logged but don't raise

Reference:
    - docs/architecture/sse-architecture.md
"""

import json
import logging
from uuid import UUID

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.constants import (
    SSE_RETENTION_MAX_LEN_DEFAULT,
    SSE_RETENTION_TTL_DEFAULT,
)
from src.domain.events.sse_event import SSEEvent
from src.infrastructure.sse.channel_keys import SSEChannelKeys


class RedisSSEPublisher:
    """Redis implementation of SSEPublisherProtocol.

    Publishes SSE events to user channels via Redis pub/sub.
    When retention is enabled, also stores in Redis Streams for replay.

    Note: Does NOT inherit from SSEPublisherProtocol (uses structural typing).

    Attributes:
        _redis: Async Redis client instance.
        _enable_retention: Whether to store events in Redis Streams.
        _retention_max_len: Max events to retain per user.
        _retention_ttl: TTL for retained events (seconds).
        _logger: Logger instance.
    """

    def __init__(
        self,
        redis_client: "Redis[bytes]",  # type: ignore[type-arg]
        enable_retention: bool = False,
        retention_max_len: int = SSE_RETENTION_MAX_LEN_DEFAULT,
        retention_ttl_seconds: int = SSE_RETENTION_TTL_DEFAULT,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize Redis SSE publisher.

        Args:
            redis_client: Async Redis client instance.
            enable_retention: Store events in Redis Streams for replay.
            retention_max_len: Max events per user stream (MAXLEN).
            retention_ttl_seconds: TTL for stream entries.
            logger: Optional logger (creates default if not provided).
        """
        self._redis = redis_client
        self._enable_retention = enable_retention
        self._retention_max_len = retention_max_len
        self._retention_ttl = retention_ttl_seconds
        self._logger = logger or logging.getLogger(__name__)

    async def publish(self, event: SSEEvent) -> None:
        """Publish SSE event to user's channel.

        Routes event to the user's Redis pub/sub channel. If retention
        is enabled, also stores in Redis Stream for replay.

        Args:
            event: SSE event to publish. Contains user_id for routing.

        Note:
            - Fail-open: Errors are logged but not raised
            - Non-blocking: Returns immediately after publish
        """
        await self.publish_to_user(event.user_id, event)

    async def publish_to_user(self, user_id: UUID, event: SSEEvent) -> None:
        """Publish SSE event to specific user's channel.

        Args:
            user_id: Target user ID.
            event: SSE event to publish.

        Note:
            Same fail-open behavior as publish().
        """
        channel = SSEChannelKeys.user_channel(user_id)

        try:
            # Serialize event to JSON for pub/sub
            event_json = json.dumps(event.to_dict())

            # Publish to pub/sub channel
            await self._redis.publish(channel, event_json)

            self._logger.debug(
                "Published SSE event",
                extra={
                    "event_type": event.event_type.value,
                    "user_id": str(user_id),
                    "event_id": str(event.event_id),
                    "channel": channel,
                },
            )

            # Store in Redis Stream if retention enabled
            if self._enable_retention:
                await self._store_in_stream(user_id, event)

        except RedisError as e:
            # Fail-open: log error but don't raise
            self._logger.warning(
                "Failed to publish SSE event (fail-open)",
                extra={
                    "event_type": event.event_type.value,
                    "user_id": str(user_id),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
        except Exception as e:
            # Catch-all for unexpected errors
            self._logger.error(
                "Unexpected error publishing SSE event (fail-open)",
                extra={
                    "event_type": event.event_type.value,
                    "user_id": str(user_id),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    async def broadcast(self, event: SSEEvent) -> None:
        """Broadcast SSE event to all connected clients.

        Publishes to the global broadcast channel.

        Args:
            event: SSE event to broadcast.

        Note:
            Event's user_id is preserved but event goes to all users.
        """
        channel = SSEChannelKeys.broadcast_channel()

        try:
            event_json = json.dumps(event.to_dict())
            await self._redis.publish(channel, event_json)

            self._logger.debug(
                "Broadcast SSE event",
                extra={
                    "event_type": event.event_type.value,
                    "event_id": str(event.event_id),
                    "channel": channel,
                },
            )

        except RedisError as e:
            self._logger.warning(
                "Failed to broadcast SSE event (fail-open)",
                extra={
                    "event_type": event.event_type.value,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
        except Exception as e:
            self._logger.error(
                "Unexpected error broadcasting SSE event (fail-open)",
                extra={
                    "event_type": event.event_type.value,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

    async def _store_in_stream(self, user_id: UUID, event: SSEEvent) -> None:
        """Store event in Redis Stream for retention.

        Called when retention is enabled. Uses XADD with MAXLEN
        to keep stream size bounded.

        Args:
            user_id: User ID for stream key.
            event: Event to store.
        """
        stream_key = SSEChannelKeys.user_stream(user_id)

        try:
            # XADD with MAXLEN to cap stream size
            # Using ~ (approximate) for better performance
            await self._redis.xadd(
                stream_key,
                {
                    "event_id": str(event.event_id),
                    "event_type": event.event_type.value,
                    "data": json.dumps(event.data),
                    "occurred_at": event.occurred_at.isoformat(),
                },
                maxlen=self._retention_max_len,
                approximate=True,
            )

            # Set TTL on stream if not already set
            # This ensures old streams get cleaned up
            ttl = await self._redis.ttl(stream_key)
            if ttl == -1:  # No TTL set
                await self._redis.expire(stream_key, self._retention_ttl)

            self._logger.debug(
                "Stored SSE event in stream",
                extra={
                    "stream_key": stream_key,
                    "event_id": str(event.event_id),
                },
            )

        except RedisError as e:
            # Fail-open: stream storage is optional
            self._logger.warning(
                "Failed to store SSE event in stream (fail-open)",
                extra={
                    "stream_key": stream_key,
                    "error": str(e),
                },
            )
