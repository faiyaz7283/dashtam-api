"""Redis implementation of CacheBackend for session management.

This is a concrete implementation of the CacheBackend interface using Redis.
Separate from rate limiter's Redis client to maintain independence.
"""

import logging
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.cache.base import CacheBackend, CacheError

logger = logging.getLogger(__name__)


class RedisCache(CacheBackend):
    """Redis implementation of cache backend for session management.

    This implementation uses Redis for token blacklist operations.
    It's separate from rate limiter's Redis to allow:
    - Different configuration (host, db, timeout)
    - Independent scaling
    - Clean separation of concerns

    Attributes:
        client: Redis async client
    """

    def __init__(self, redis_client: Redis):
        """Initialize Redis cache with client.

        Args:
            redis_client: Async Redis client instance
        """
        self.client = redis_client
        logger.info("Redis cache initialized for session management")

    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Set key-value pair with TTL in Redis.

        Args:
            key: Cache key
            value: Cache value
            ttl_seconds: Time to live in seconds

        Raises:
            CacheError: If Redis operation fails
        """
        try:
            await self.client.setex(key, ttl_seconds, value)
            logger.debug(f"Cache set: {key} (TTL: {ttl_seconds}s)")
        except RedisError as e:
            logger.error(f"Redis SET failed for key {key}: {e}")
            raise CacheError(f"Failed to set cache key: {key}") from e

    async def get(self, key: str) -> Optional[str]:
        """Get value by key from Redis.

        Args:
            key: Cache key

        Returns:
            Value if exists, None otherwise

        Raises:
            CacheError: If Redis operation fails
        """
        try:
            value = await self.client.get(key)
            logger.debug(f"Cache get: {key} = {value}")
            return value
        except RedisError as e:
            logger.error(f"Redis GET failed for key {key}: {e}")
            raise CacheError(f"Failed to get cache key: {key}") from e

    async def delete(self, key: str) -> None:
        """Delete key from Redis.

        Args:
            key: Cache key

        Raises:
            CacheError: If Redis operation fails
        """
        try:
            await self.client.delete(key)
            logger.debug(f"Cache delete: {key}")
        except RedisError as e:
            logger.error(f"Redis DELETE failed for key {key}: {e}")
            raise CacheError(f"Failed to delete cache key: {key}") from e

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise

        Raises:
            CacheError: If Redis operation fails
        """
        try:
            result = await self.client.exists(key)
            exists = result > 0
            logger.debug(f"Cache exists: {key} = {exists}")
            return exists
        except RedisError as e:
            logger.error(f"Redis EXISTS failed for key {key}: {e}")
            raise CacheError(f"Failed to check cache key existence: {key}") from e

    async def close(self) -> None:
        """Close Redis connection.

        Should be called during application shutdown.
        """
        try:
            await self.client.aclose()
            logger.info("Redis cache connection closed")
        except RedisError as e:
            logger.warning(f"Error closing Redis connection: {e}")
