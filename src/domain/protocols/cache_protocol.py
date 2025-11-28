"""Cache protocol for domain layer.

This module defines the cache interface that the domain needs, without knowing
about any specific implementation. Infrastructure adapters implement this
protocol to provide caching functionality.

Architecture:
- Protocol-based - uses structural typing
- TypedDict for internal cache metadata
- All operations return Result types
- No framework dependencies in domain layer
"""

from typing import Any, Protocol, TypedDict

from src.core.errors import DomainError
from src.core.result import Result


class CacheEntry(TypedDict):
    """Internal cache entry metadata.

    Used internally by cache adapters to track cache state.
    NOT exposed to domain services (they just get string values).

    Attributes:
        key: Cache key.
        value: Cached value (string).
        ttl: Time to live in seconds (None = no expiration).
        created_at: Unix timestamp when entry was created.
        expires_at: Unix timestamp when entry expires (None if no TTL).
    """

    key: str
    value: str
    ttl: int | None
    created_at: float
    expires_at: float | None


class CacheProtocol(Protocol):
    """Cache protocol - what domain needs from cache.

    Defines caching operations using Protocol (structural typing).
    Infrastructure adapters implement this without inheritance.

    All operations return Result types for error handling.
    Fail-open strategy: cache failures should not break core functionality.
    """

    async def get(self, key: str) -> Result[str | None, DomainError]:
        """Get value from cache.

        Args:
            key: Cache key.

        Returns:
            Result with value if found, None if not found, or CacheError.

        Example:
            result = await cache.get("user:123")
            match result:
                case Success(value) if value:
                    # Key found
                    user_data = json.loads(value)
                case Success(None):
                    # Key not found (cache miss)
                    pass
                case Failure(error):
                    # Cache error - fail open
                    logger.warning("Cache get failed", error=error)
        """
        ...

    async def get_json(self, key: str) -> Result[dict[str, Any] | None, DomainError]:
        """Get JSON value from cache.

        Convenience method that deserializes JSON automatically.

        Args:
            key: Cache key.

        Returns:
            Result with parsed dict if found, None if not found, or CacheError.

        Example:
            result = await cache.get_json("user:123")
            match result:
                case Success(data) if data:
                    user_id = data["id"]
                case Success(None):
                    # Cache miss
                    pass
                case Failure(_):
                    # Fail open
                    pass
        """
        ...

    async def set(
        self,
        key: str,
        value: str,
        ttl: int | None = None,
    ) -> Result[None, DomainError]:
        """Set value in cache.

        Args:
            key: Cache key.
            value: Value to cache (string).
            ttl: Time to live in seconds (None = no expiration).

        Returns:
            Result with None on success, or CacheError.

        Example:
            result = await cache.set(
                "user:123",
                json.dumps(user_data),
                ttl=3600  # 1 hour
            )
            match result:
                case Success(_):
                    # Cached successfully
                    pass
                case Failure(_):
                    # Fail open - continue without cache
                    pass
        """
        ...

    async def set_json(
        self,
        key: str,
        value: dict[str, Any],
        ttl: int | None = None,
    ) -> Result[None, DomainError]:
        """Set JSON value in cache.

        Convenience method that serializes dict to JSON automatically.

        Args:
            key: Cache key.
            value: Dict to cache (will be JSON serialized).
            ttl: Time to live in seconds (None = no expiration).

        Returns:
            Result with None on success, or CacheError.

        Example:
            result = await cache.set_json(
                "user:123",
                {"id": "123", "email": "user@example.com"},
                ttl=1800  # 30 minutes
            )
        """
        ...

    async def delete(self, key: str) -> Result[bool, DomainError]:
        """Delete key from cache.

        Args:
            key: Cache key to delete.

        Returns:
            Result with True if key was deleted, False if key didn't exist,
            or CacheError.

        Example:
            result = await cache.delete("user:123")
            match result:
                case Success(True):
                    # Key was deleted
                    pass
                case Success(False):
                    # Key didn't exist
                    pass
                case Failure(_):
                    # Fail open
                    pass
        """
        ...

    async def exists(self, key: str) -> Result[bool, DomainError]:
        """Check if key exists in cache.

        Args:
            key: Cache key to check.

        Returns:
            Result with True if key exists, False if not, or CacheError.

        Example:
            result = await cache.exists("user:123")
            match result:
                case Success(True):
                    # Key exists
                    pass
                case Success(False):
                    # Key doesn't exist
                    pass
                case Failure(_):
                    # Fail open - assume doesn't exist
                    pass
        """
        ...

    async def expire(self, key: str, seconds: int) -> Result[bool, DomainError]:
        """Set expiration time on key.

        Args:
            key: Cache key.
            seconds: Seconds until expiration.

        Returns:
            Result with True if timeout was set, False if key doesn't exist,
            or CacheError.

        Example:
            result = await cache.expire("session:abc", 1800)
            match result:
                case Success(True):
                    # Expiration set
                    pass
                case Success(False):
                    # Key doesn't exist
                    pass
                case Failure(_):
                    # Fail open
                    pass
        """
        ...

    async def ttl(self, key: str) -> Result[int | None, DomainError]:
        """Get time to live for key.

        Args:
            key: Cache key.

        Returns:
            Result with seconds until expiration, None if no TTL or key doesn't
            exist, or CacheError.

        Example:
            result = await cache.ttl("session:abc")
            match result:
                case Success(seconds) if seconds:
                    # Key expires in `seconds`
                    pass
                case Success(None):
                    # No TTL or key doesn't exist
                    pass
                case Failure(_):
                    # Fail open
                    pass
        """
        ...

    async def increment(self, key: str, amount: int = 1) -> Result[int, DomainError]:
        """Increment numeric value in cache (atomic).

        If key doesn't exist, it's created with value = amount.

        Args:
            key: Cache key.
            amount: Amount to increment by (default: 1).

        Returns:
            Result with new value after increment, or CacheError.

        Example (rate limiting):
            result = await cache.increment(f"rate_limit:{user_id}:{endpoint}")
            match result:
                case Success(count) if count == 1:
                    # First request - set expiration
                    await cache.expire(key, 60)
                case Success(count) if count > 100:
                    # Rate limit exceeded
                    raise RateLimitError()
                case Failure(_):
                    # Fail open - allow request
                    pass
        """
        ...

    async def decrement(self, key: str, amount: int = 1) -> Result[int, DomainError]:
        """Decrement numeric value in cache (atomic).

        Args:
            key: Cache key.
            amount: Amount to decrement by (default: 1).

        Returns:
            Result with new value after decrement, or CacheError.
        """
        ...

    async def flush(self) -> Result[None, DomainError]:
        """Flush all keys from cache.

        WARNING: Use with extreme caution! This clears ALL cache data.
        Should only be used in tests or maintenance windows.

        Returns:
            Result with None on success, or CacheError.

        Example (tests only):
            await cache.flush()  # Clear cache between tests
        """
        ...

    async def ping(self) -> Result[bool, DomainError]:
        """Check cache connectivity (health check).

        Returns:
            Result with True if cache is reachable, or CacheError.

        Example:
            result = await cache.ping()
            match result:
                case Success(True):
                    # Cache is healthy
                    pass
                case Failure(_):
                    # Cache unreachable
                    logger.error("Cache health check failed")
        """
        ...

    async def delete_pattern(self, pattern: str) -> Result[int, DomainError]:
        """Delete all keys matching pattern.

        Args:
            pattern: Glob-style pattern (e.g., "authz:user123:*").

        Returns:
            Result with number of keys deleted, or CacheError.

        Example:
            result = await cache.delete_pattern("session:user123:*")
            match result:
                case Success(count):
                    logger.info(f"Deleted {count} keys")
                case Failure(_):
                    # Fail open
                    pass
        """
        ...
