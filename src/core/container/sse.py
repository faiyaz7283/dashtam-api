"""SSE dependency factories.

Application-scoped singletons and request-scoped factories for SSE:
- get_sse_publisher(): App-scoped singleton for publishing SSE events
- get_sse_subscriber(): Request-scoped factory for SSE stream subscriptions

Reference:
    - docs/architecture/sse-architecture.md (Section 6)
"""

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.protocols.sse_publisher_protocol import SSEPublisherProtocol
    from src.infrastructure.sse.redis_subscriber import RedisSSESubscriber


@lru_cache()
def get_sse_publisher() -> "SSEPublisherProtocol":
    """Get SSE publisher singleton (app-scoped).

    Returns RedisSSEPublisher with shared Redis connection pool.
    Uses same Redis connection as cache for efficiency.

    Returns:
        SSE publisher implementing SSEPublisherProtocol.

    Usage:
        # Application Layer (direct use in handlers)
        publisher = get_sse_publisher()
        await publisher.publish(event)

        # Infrastructure Layer (event handler wiring)
        sse_handler = SSEEventHandler(publisher=get_sse_publisher())
    """
    from redis.asyncio import ConnectionPool, Redis

    from src.core.config import get_settings
    from src.core.constants import (
        SSE_RETENTION_MAX_LEN_DEFAULT,
        SSE_RETENTION_TTL_DEFAULT,
    )
    from src.infrastructure.sse.redis_publisher import RedisSSEPublisher

    settings = get_settings()

    # Create dedicated Redis connection pool for SSE pub/sub
    # Pub/sub uses long-lived connections, so separate pool is cleaner
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=20,  # Fewer connections than cache (pub/sub is lighter)
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
        socket_keepalive=True,
    )
    redis_client: Redis[bytes] = Redis(connection_pool=pool)  # type: ignore[type-arg]

    return RedisSSEPublisher(
        redis_client=redis_client,
        enable_retention=settings.sse_enable_retention,
        retention_max_len=SSE_RETENTION_MAX_LEN_DEFAULT,
        retention_ttl_seconds=SSE_RETENTION_TTL_DEFAULT,
    )


def get_sse_subscriber() -> "RedisSSESubscriber":
    """Get SSE subscriber (request-scoped).

    Returns new RedisSSESubscriber instance for each SSE connection.
    Each subscriber manages its own pub/sub subscription lifecycle.

    Returns:
        New RedisSSESubscriber instance.

    Note:
        NOT a singleton - each SSE connection gets its own subscriber.
        This is intentional: pub/sub subscriptions are per-connection.

    Usage:
        # Presentation Layer (FastAPI Depends in SSE endpoint)
        subscriber = get_sse_subscriber()
        async for event in subscriber.subscribe(user_id):
            yield event.to_sse_format()
    """
    from redis.asyncio import ConnectionPool, Redis

    from src.core.config import get_settings
    from src.infrastructure.sse.redis_subscriber import RedisSSESubscriber

    settings = get_settings()

    # Create new Redis client for this subscriber
    # Each subscriber needs its own connection for pub/sub
    pool = ConnectionPool.from_url(
        settings.redis_url,
        max_connections=5,  # Small pool per subscriber
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=None,  # No timeout for pub/sub (long-lived)
        socket_keepalive=True,
    )
    redis_client: Redis[bytes] = Redis(connection_pool=pool)  # type: ignore[type-arg]

    return RedisSSESubscriber(
        redis_client=redis_client,
        enable_retention=settings.sse_enable_retention,
    )
