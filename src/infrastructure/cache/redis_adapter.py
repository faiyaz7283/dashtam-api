"""Redis adapter implementing CacheProtocol.

This adapter provides Redis-specific implementation of the cache protocol
defined in the domain layer. It wraps the Redis client and handles all
Redis-specific operations and error mapping.

Architecture:
- Implements CacheProtocol without inheritance (structural typing)
- Maps Redis exceptions to CacheError with proper ErrorCode
- Returns Result types for all operations
- Fail-open strategy for resilience
"""

import json
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.core.enums import ErrorCode
from src.core.result import Failure, Result, Success
from src.infrastructure.enums import InfrastructureErrorCode
from src.infrastructure.errors import CacheError


class RedisAdapter:
    """Redis implementation of CacheProtocol.

    This adapter wraps an async Redis client and implements all cache
    operations defined in CacheProtocol. It handles Redis-specific
    exceptions and maps them to domain-appropriate errors.

    Note: Does NOT inherit from CacheProtocol (uses structural typing).

    Attributes:
        _redis: Async Redis client instance.
    """

    def __init__(self, redis_client: Redis) -> None:
        """Initialize Redis adapter.

        Args:
            redis_client: Async Redis client instance.
        """
        self._redis = redis_client

    async def get(self, key: str) -> Result[str | None, CacheError]:
        """Get value from Redis.

        Args:
            key: Cache key.

        Returns:
            Result with value if found, None if not found, or CacheError.
        """
        try:
            value = await self._redis.get(key)
            # Redis returns bytes or None
            if value is None:
                return Success(value=None)
            decoded = value.decode("utf-8") if isinstance(value, bytes) else value
            return Success(value=decoded)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_GET_ERROR,
                    message=f"Failed to get key '{key}' from cache",
                    details={"key": key, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_GET_ERROR,
                    message=f"Unexpected error getting key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def get_json(self, key: str) -> Result[dict[str, Any] | None, CacheError]:
        """Get JSON value from Redis.

        Args:
            key: Cache key.

        Returns:
            Result with parsed dict if found, None if not found, or CacheError.
        """
        result = await self.get(key)

        match result:
            case Success(value=None):
                return Success(value=None)
            case Success(value=val) if val is not None:
                try:
                    parsed = json.loads(val)
                    return Success(value=parsed)
                except json.JSONDecodeError as e:
                    return Failure(
                        error=CacheError(
                            code=ErrorCode.VALIDATION_FAILED,
                            infrastructure_code=InfrastructureErrorCode.CACHE_GET_ERROR,
                            message=f"Failed to parse JSON for key '{key}'",
                            details={"key": key, "error": str(e)},
                        )
                    )
            case Failure(error=err):
                return Failure(error=err)
            case _:
                # Unreachable but needed for type checker
                return Success(value=None)

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> Result[None, CacheError]:
        """Set value in Redis.

        Args:
            key: Cache key.
            value: Value to cache.
            ttl: Time to live in seconds (None = no expiration).

        Returns:
            Result with None on success, or CacheError.
        """
        try:
            if ttl is not None:
                await self._redis.setex(key, ttl, value)
            else:
                await self._redis.set(key, value)
            return Success(value=None)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Failed to set key '{key}' in cache",
                    details={"key": key, "ttl": ttl, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Unexpected error setting key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def set_json(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> Result[None, CacheError]:
        """Set JSON value in Redis.

        Args:
            key: Cache key.
            value: Dict to cache (will be JSON serialized).
            ttl: Time to live in seconds (None = no expiration).

        Returns:
            Result with None on success, or CacheError.
        """
        try:
            serialized = json.dumps(value)
            return await self.set(key, serialized, ttl)
        except (TypeError, ValueError) as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Failed to serialize value for key '{key}'",
                    details={"key": key, "error": str(e)},
                )
            )

    async def delete(self, key: str) -> Result[bool, CacheError]:
        """Delete key from Redis.

        Args:
            key: Cache key to delete.

        Returns:
            Result with True if deleted, False if key didn't exist, or CacheError.
        """
        try:
            deleted_count = await self._redis.delete(key)
            return Success(value=deleted_count > 0)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_DELETE_ERROR,
                    message=f"Failed to delete key '{key}' from cache",
                    details={"key": key, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_DELETE_ERROR,
                    message=f"Unexpected error deleting key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def exists(self, key: str) -> Result[bool, CacheError]:
        """Check if key exists in Redis.

        Args:
            key: Cache key to check.

        Returns:
            Result with True if exists, False if not, or CacheError.
        """
        try:
            exists_count = await self._redis.exists(key)
            return Success(value=exists_count > 0)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_GET_ERROR,
                    message=f"Failed to check existence of key '{key}'",
                    details={"key": key, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_GET_ERROR,
                    message=f"Unexpected error checking key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def expire(self, key: str, seconds: int) -> Result[bool, CacheError]:
        """Set expiration on key in Redis.

        Args:
            key: Cache key.
            seconds: Seconds until expiration.

        Returns:
            Result with True if timeout set, False if key doesn't exist, or CacheError.
        """
        try:
            was_set = await self._redis.expire(key, seconds)
            return Success(value=bool(was_set))
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Failed to set expiration on key '{key}'",
                    details={"key": key, "seconds": seconds, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Unexpected error setting expiration on key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def ttl(self, key: str) -> Result[int | None, CacheError]:
        """Get time to live for key in Redis.

        Args:
            key: Cache key.

        Returns:
            Result with seconds until expiration, None if no TTL or key doesn't exist, or CacheError.
        """
        try:
            ttl_value = await self._redis.ttl(key)
            # Redis returns -2 if key doesn't exist, -1 if no expiration
            if ttl_value == -2 or ttl_value == -1:
                return Success(value=None)
            return Success(value=ttl_value)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_GET_ERROR,
                    message=f"Failed to get TTL for key '{key}'",
                    details={"key": key, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_GET_ERROR,
                    message=f"Unexpected error getting TTL for key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def increment(self, key: str, amount: int = 1) -> Result[int, CacheError]:
        """Increment value in Redis (atomic).

        Args:
            key: Cache key.
            amount: Amount to increment by.

        Returns:
            Result with new value after increment, or CacheError.
        """
        try:
            new_value = await self._redis.incrby(key, amount)
            return Success(value=new_value)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Failed to increment key '{key}'",
                    details={"key": key, "amount": amount, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Unexpected error incrementing key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def decrement(self, key: str, amount: int = 1) -> Result[int, CacheError]:
        """Decrement value in Redis (atomic).

        Args:
            key: Cache key.
            amount: Amount to decrement by.

        Returns:
            Result with new value after decrement, or CacheError.
        """
        try:
            new_value = await self._redis.decrby(key, amount)
            return Success(value=new_value)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Failed to decrement key '{key}'",
                    details={"key": key, "amount": amount, "error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_SET_ERROR,
                    message=f"Unexpected error decrementing key '{key}'",
                    details={"key": key, "error": str(e), "type": type(e).__name__},
                )
            )

    async def flush(self) -> Result[None, CacheError]:
        """Flush all keys from Redis.

        WARNING: Clears ALL cache data! Use only in tests.

        Returns:
            Result with None on success, or CacheError.
        """
        try:
            await self._redis.flushdb()
            return Success(value=None)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_DELETE_ERROR,
                    message="Failed to flush cache",
                    details={"error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_DELETE_ERROR,
                    message="Unexpected error flushing cache",
                    details={"error": str(e), "type": type(e).__name__},
                )
            )

    async def ping(self) -> Result[bool, CacheError]:
        """Check Redis connectivity (health check).

        Returns:
            Result with True if Redis is reachable, or CacheError.
        """
        try:
            # ping() returns True if successful
            # Type ignore due to redis.asyncio ping() return type ambiguity
            await self._redis.ping()  # type: ignore[misc]
            return Success(value=True)
        except RedisError as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_CONNECTION_ERROR,
                    message="Redis health check failed",
                    details={"error": str(e)},
                )
            )
        except Exception as e:
            return Failure(
                error=CacheError(
                    code=ErrorCode.VALIDATION_FAILED,
                    infrastructure_code=InfrastructureErrorCode.CACHE_CONNECTION_ERROR,
                    message="Unexpected error during Redis health check",
                    details={"error": str(e), "type": type(e).__name__},
                )
            )
