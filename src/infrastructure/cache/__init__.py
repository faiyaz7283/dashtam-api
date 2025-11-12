"""Cache infrastructure package.

This module provides cache client management and dependency injection
for the cache system. It follows the singleton pattern to ensure a
single Redis connection pool is shared across the application.

Architecture:
- Singleton Redis client with connection pooling
- Factory functions for dependency injection
- Health check support
"""

from typing import cast

from redis.asyncio import ConnectionPool, Redis

from src.core.config import settings
from src.domain.protocols.cache import CacheProtocol
from src.infrastructure.cache.redis_adapter import RedisAdapter

# Global Redis client instance (singleton)
_redis_client: Redis | None = None
_cache_adapter: RedisAdapter | None = None


def get_redis_client() -> Redis:
    """Get or create Redis client singleton.

    Creates a Redis client with connection pooling on first call,
    then returns the same instance on subsequent calls.

    Returns:
        Async Redis client instance.

    Example:
        redis = get_redis_client()
        await redis.ping()
    """
    global _redis_client

    if _redis_client is None:
        # Create connection pool
        pool = ConnectionPool.from_url(
            settings.redis_url,
            max_connections=50,
            decode_responses=False,  # We handle decoding in adapter
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={
                1: 1,  # TCP_KEEPIDLE
                2: 1,  # TCP_KEEPINTVL
                3: 5,  # TCP_KEEPCNT
            },
        )
        _redis_client = Redis(connection_pool=pool)

    return _redis_client


def get_cache() -> CacheProtocol:
    """Get or create cache adapter singleton.

    Returns RedisAdapter that implements CacheProtocol.
    Uses singleton pattern to share connection pool.

    Returns:
        Cache adapter implementing CacheProtocol.

    Example:
        cache = get_cache()
        result = await cache.get("key")
    """
    global _cache_adapter

    if _cache_adapter is None:
        redis = get_redis_client()
        _cache_adapter = RedisAdapter(redis_client=redis)

    # Cast to CacheProtocol for type safety (structural typing)
    return cast(CacheProtocol, _cache_adapter)


async def close_redis_client() -> None:
    """Close Redis client and connection pool.

    Should be called during application shutdown to clean up resources.

    Example:
        await close_redis_client()
    """
    global _redis_client, _cache_adapter

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        _cache_adapter = None


async def health_check() -> bool:
    """Check Redis connectivity.

    Returns:
        True if Redis is reachable, False otherwise.

    Example:
        is_healthy = await health_check()
        if not is_healthy:
            logger.error("Redis is unhealthy")
    """
    try:
        cache = get_cache()
        result = await cache.ping()

        # Result pattern - check if successful
        match result:
            case {"value": True}:
                return True
            case _:
                return False
    except Exception:
        return False


__all__ = [
    "get_redis_client",
    "get_cache",
    "close_redis_client",
    "health_check",
]
