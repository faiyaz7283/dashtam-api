"""Provider connection cache protocol for fast lookups.

This module defines the port (interface) for provider connection caching.
Infrastructure layer implements with Redis for <5ms lookups.

Reference:
    - docs/architecture/cache-key-patterns.md
"""

from typing import Protocol
from uuid import UUID

from src.domain.entities.provider_connection import ProviderConnection


class ProviderConnectionCache(Protocol):
    """Provider connection cache protocol (port) for fast lookups.

    Provides <5ms provider connection lookups via Redis caching.
    Reduces database queries for connection status checks.

    Cache Strategy:
        - Connection data cached on reads
        - Cache invalidated on updates/disconnects
        - TTL: 5 minutes (configurable via CACHE_PROVIDER_TTL)
        - Database is source of truth

    Key Patterns:
        - provider:conn:{connection_id} -> ProviderConnection entity

    Example:
        >>> class RedisProviderConnectionCache:
        ...     async def get(self, connection_id: UUID) -> ProviderConnection | None:
        ...         # Look up in Redis
        ...         ...
        ...     async def set(self, connection: ProviderConnection) -> None:
        ...         # Store in Redis with TTL
        ...         ...
    """

    async def get(self, connection_id: UUID) -> ProviderConnection | None:
        """Get provider connection from cache.

        Args:
            connection_id: Provider connection identifier.

        Returns:
            ProviderConnection if cached, None otherwise.
        """
        ...

    async def set(
        self,
        connection: ProviderConnection,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        """Store provider connection in cache.

        Args:
            connection: Provider connection to cache.
            ttl_seconds: Cache TTL in seconds. If None, uses CACHE_PROVIDER_TTL from settings.
        """
        ...

    async def delete(self, connection_id: UUID) -> bool:
        """Remove provider connection from cache.

        Called when connection is updated, disconnected, or deleted.

        Args:
            connection_id: Provider connection identifier.

        Returns:
            True if deleted, False if not found.
        """
        ...

    async def exists(self, connection_id: UUID) -> bool:
        """Check if provider connection exists in cache.

        Faster than full get() when only existence check needed.

        Args:
            connection_id: Provider connection identifier.

        Returns:
            True if connection exists in cache, False otherwise.
        """
        ...
