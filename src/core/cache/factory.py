"""Cache factory for session management Redis client.

SOLID Principles:
- Dependency Inversion: Factory creates concrete implementation, services depend on abstraction
- Single Responsibility: Factory only responsible for cache creation and lifecycle

Design Decision:
- Separate Redis client from rate limiter
- Session management uses Redis DB 1 (rate limiter uses DB 0)
- Allows independent configuration and scaling
- Maintains clean separation of concerns
"""

import logging
from typing import Optional

from redis.asyncio import Redis

from src.core.cache.base import CacheBackend
from src.core.cache.redis_cache import RedisCache
from src.core.config import get_settings

logger = logging.getLogger(__name__)

# Singleton cache instance
_cache_instance: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get singleton cache instance for session management.

    This factory creates a Redis cache client separate from rate limiter's Redis.
    Configuration differences:
    - Session management: DB 1 (this cache)
    - Rate limiter: DB 0 (independent client)

    Returns:
        CacheBackend instance (RedisCache)

    Example:
        >>> cache = get_cache()
        >>> await cache.set("revoked_token:uuid", "1", 2592000)
    """
    global _cache_instance

    if _cache_instance is None:
        settings = get_settings()

        # Create Redis client for session management
        # Uses DB 1 (rate limiter uses DB 0 for independence)
        redis_client = Redis(
            host=getattr(settings, "REDIS_HOST", "redis"),
            port=getattr(settings, "REDIS_PORT", 6379),
            db=1,  # Separate DB from rate limiter (which uses DB 0)
            decode_responses=True,  # Return strings, not bytes
            socket_connect_timeout=5,
            socket_timeout=5,
        )

        _cache_instance = RedisCache(redis_client)
        logger.info("Session management cache initialized (Redis DB 1)")

    return _cache_instance


async def close_cache() -> None:
    """Close cache connection and cleanup resources.

    Should be called during application shutdown.
    """
    global _cache_instance

    if _cache_instance is not None:
        await _cache_instance.close()
        _cache_instance = None
        logger.info("Session management cache closed")
