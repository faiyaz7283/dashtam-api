"""SSE Infrastructure adapters package.

This package contains Redis-backed implementations of SSE protocols:
- RedisSSEPublisher: Publishes SSE events via Redis pub/sub
- RedisSSESubscriber: Subscribes to SSE event streams
- SSEChannelKeys: Redis channel naming conventions
- SSEEventHandler: Bridges domain events to SSE (app-scoped singleton)

Architecture:
    - Implements domain protocols without inheritance (structural typing)
    - Uses Redis pub/sub for horizontal scaling
    - Optional Redis Streams for event retention (Last-Event-ID replay)
    - Fail-open design: SSE failures don't break core API

Reference:
    - docs/architecture/sse-architecture.md
"""

from src.infrastructure.sse.channel_keys import SSEChannelKeys
from src.infrastructure.sse.redis_publisher import RedisSSEPublisher
from src.infrastructure.sse.redis_subscriber import RedisSSESubscriber
from src.infrastructure.sse.sse_event_handler import SSEEventHandler

__all__ = [
    "SSEChannelKeys",
    "RedisSSEPublisher",
    "RedisSSESubscriber",
    "SSEEventHandler",
]
