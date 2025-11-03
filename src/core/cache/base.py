"""Cache abstraction interface for session management and caching.

SOLID Principles:
- Interface Segregation: Minimal interface for session token blacklist operations
- Dependency Inversion: High-level session management services depend on abstraction, not Redis
- Single Responsibility: Cache operations only (no business logic)

Design Decision:
- Separate from rate limiter's Redis (different concerns, different lifecycle)
- Session management: token blacklist (30-day TTL)
- Rate limiter: request counts (1-60 minute TTL)

This allows:
- Easy testing (mock cache implementation)
- Future migration to different cache backend (Memcached, DynamoDB, etc.)
- No coupling to Redis implementation details
"""

from abc import ABC, abstractmethod
from typing import Optional


class CacheBackend(ABC):
    """Abstract cache backend for session management.

    This interface defines minimal operations needed for session token blacklist.
    Implementations can use Redis, Memcached, or in-memory storage.
    """

    @abstractmethod
    async def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Set key-value pair with TTL.

        Args:
            key: Cache key (e.g., 'revoked_token:uuid')
            value: Cache value (e.g., '1' for blacklist flag)
            ttl_seconds: Time to live in seconds

        Raises:
            CacheError: If cache operation fails
        """
        pass

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Get value by key.

        Args:
            key: Cache key

        Returns:
            Value if exists, None otherwise

        Raises:
            CacheError: If cache operation fails
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key from cache.

        Args:
            key: Cache key

        Raises:
            CacheError: If cache operation fails
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise

        Raises:
            CacheError: If cache operation fails
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close cache connection and cleanup resources.

        Should be called during application shutdown.
        """
        pass


class CacheError(Exception):
    """Base exception for cache operations."""

    pass
