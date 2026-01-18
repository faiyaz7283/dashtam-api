"""Redis SSE Subscriber implementing SSESubscriberProtocol.

This adapter subscribes to SSE events via Redis pub/sub and yields them
as an async generator. Supports category filtering and Last-Event-ID
replay from Redis Streams.

Architecture:
    - Implements SSESubscriberProtocol without inheritance (structural typing)
    - Uses Redis pub/sub for real-time event delivery
    - Async generator pattern for streaming
    - Optional Redis Streams for missed event replay

Reference:
    - docs/architecture/sse-architecture.md
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

from redis.asyncio import Redis
from redis.asyncio.client import PubSub
from redis.exceptions import RedisError

from src.domain.events.sse_event import SSEEvent, SSEEventCategory, SSEEventType
from src.infrastructure.sse.channel_keys import SSEChannelKeys


class RedisSSESubscriber:
    """Redis implementation of SSESubscriberProtocol.

    Subscribes to user and broadcast channels via Redis pub/sub,
    yielding events as they arrive. Supports category filtering
    and replay of missed events from Redis Streams.

    Note: Does NOT inherit from SSESubscriberProtocol (uses structural typing).

    Attributes:
        _redis: Async Redis client instance.
        _enable_retention: Whether retention is available for replay.
        _logger: Logger instance.
    """

    def __init__(
        self,
        redis_client: "Redis[bytes]",  # type: ignore[type-arg]
        enable_retention: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize Redis SSE subscriber.

        Args:
            redis_client: Async Redis client instance.
            enable_retention: Whether retention is enabled for replay.
            logger: Optional logger (creates default if not provided).
        """
        self._redis = redis_client
        self._enable_retention = enable_retention
        self._logger = logger or logging.getLogger(__name__)

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

        Yields:
            SSEEvent: Events matching the subscription criteria.
        """
        user_channel = SSEChannelKeys.user_channel(user_id)
        broadcast_channel = SSEChannelKeys.broadcast_channel()

        # Validate categories if provided
        valid_categories = self.validate_categories(categories)

        pubsub: PubSub = self._redis.pubsub()

        try:
            # Subscribe to both channels
            await pubsub.subscribe(user_channel, broadcast_channel)

            self._logger.debug(
                "Subscribed to SSE channels",
                extra={
                    "user_id": str(user_id),
                    "channels": [user_channel, broadcast_channel],
                    "categories": [c.value for c in valid_categories]
                    if valid_categories
                    else "all",
                },
            )

            # Yield events as they arrive
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                try:
                    # Parse event from JSON
                    event_data = json.loads(message["data"])
                    event = SSEEvent.from_dict(event_data)

                    # Apply category filter
                    if self.filter_by_categories(event, categories):
                        yield event

                except json.JSONDecodeError as e:
                    self._logger.warning(
                        "Failed to parse SSE event message",
                        extra={"error": str(e)},
                    )
                except (KeyError, ValueError) as e:
                    self._logger.warning(
                        "Invalid SSE event data",
                        extra={"error": str(e)},
                    )

        except RedisError as e:
            self._logger.error(
                "Redis error in SSE subscription",
                extra={
                    "user_id": str(user_id),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
        except asyncio.CancelledError:
            # Normal cancellation (client disconnect)
            self._logger.debug(
                "SSE subscription cancelled",
                extra={"user_id": str(user_id)},
            )
        finally:
            # Clean up subscription
            try:
                await pubsub.unsubscribe(user_channel, broadcast_channel)
                await pubsub.aclose()  # type: ignore[no-untyped-call]
            except Exception as e:
                self._logger.warning(
                    "Error cleaning up SSE subscription",
                    extra={"error": str(e)},
                )

    async def get_missed_events(
        self,
        user_id: UUID,
        last_event_id: UUID,
        categories: list[str] | None = None,
    ) -> list[SSEEvent]:
        """Get events missed since last_event_id.

        When a client reconnects with Last-Event-ID, retrieves events
        that were published while disconnected.

        Args:
            user_id: User ID to get events for.
            last_event_id: Last event ID received by client.
            categories: Optional category filter.

        Returns:
            List of SSEEvent objects published after last_event_id.
            Empty list if retention disabled or no events found.
        """
        if not self._enable_retention:
            return []

        stream_key = SSEChannelKeys.user_stream(user_id)
        events: list[SSEEvent] = []

        try:
            # Read all entries from stream
            # We'll filter by event_id after reading
            entries = await self._redis.xrange(stream_key, "-", "+")

            found_last = False
            for entry_id, entry_data in entries:
                event_id_str = entry_data.get(
                    b"event_id", entry_data.get("event_id", "")
                )
                if isinstance(event_id_str, bytes):
                    event_id_str = event_id_str.decode("utf-8")

                # Skip until we find the last seen event
                if not found_last:
                    if event_id_str == str(last_event_id):
                        found_last = True
                    continue

                # Parse event from stream entry
                try:
                    event = self._parse_stream_entry(entry_data, user_id)

                    # Apply category filter
                    if self.filter_by_categories(event, categories):
                        events.append(event)

                except (KeyError, ValueError) as e:
                    self._logger.warning(
                        "Failed to parse stream entry",
                        extra={"error": str(e), "entry_id": entry_id},
                    )

            self._logger.debug(
                "Retrieved missed events from stream",
                extra={
                    "user_id": str(user_id),
                    "last_event_id": str(last_event_id),
                    "count": len(events),
                },
            )

            return events

        except RedisError as e:
            self._logger.warning(
                "Failed to get missed events from stream",
                extra={
                    "user_id": str(user_id),
                    "error": str(e),
                },
            )
            return []

    def _parse_stream_entry(
        self,
        entry_data: dict[bytes | str, bytes | str],
        user_id: UUID,
    ) -> SSEEvent:
        """Parse SSEEvent from Redis Stream entry.

        Args:
            entry_data: Raw entry data from XRANGE.
            user_id: User ID (not stored in stream, passed in).

        Returns:
            Parsed SSEEvent.

        Raises:
            KeyError: If required fields missing.
            ValueError: If field values invalid.
        """

        def get_str(key: str) -> str:
            val = entry_data.get(key.encode(), entry_data.get(key, ""))
            return val.decode("utf-8") if isinstance(val, bytes) else str(val)

        event_id = UUID(get_str("event_id"))
        event_type = SSEEventType(get_str("event_type"))
        data = json.loads(get_str("data"))
        occurred_at = datetime.fromisoformat(get_str("occurred_at"))

        return SSEEvent(
            event_id=event_id,
            event_type=event_type,
            user_id=user_id,
            data=data,
            occurred_at=occurred_at,
        )

    def filter_by_categories(
        self,
        event: SSEEvent,
        categories: list[str] | None,
    ) -> bool:
        """Check if event matches category filter.

        Args:
            event: Event to check.
            categories: List of category strings to match.

        Returns:
            True if event matches filter, False otherwise.
        """
        if categories is None:
            return True

        return event.category.value in categories

    @staticmethod
    def validate_categories(categories: list[str] | None) -> list[SSEEventCategory]:
        """Validate and convert category strings to enum values.

        Args:
            categories: List of category strings from query params.

        Returns:
            List of valid SSEEventCategory enum values.

        Raises:
            ValueError: If any category string is invalid.
        """
        if categories is None:
            return []

        valid: list[SSEEventCategory] = []
        for cat_str in categories:
            try:
                valid.append(SSEEventCategory(cat_str))
            except ValueError:
                valid_names = [c.value for c in SSEEventCategory]
                raise ValueError(
                    f"Invalid category '{cat_str}'. Valid categories: {valid_names}"
                )

        return valid
