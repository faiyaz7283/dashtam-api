"""Cache keys protocol for key generation.

Defines the port for cache key construction. Infrastructure
layer implements this protocol to provide consistent key patterns.

Architecture:
    - Domain layer protocol (port)
    - Infrastructure adapter: src/infrastructure/cache/cache_keys.py
    - Used by handlers for cache key generation

Reference:
    - docs/architecture/hexagonal.md
    - docs/architecture/caching-architecture.md
"""

from datetime import date
from typing import Protocol
from uuid import UUID


class CacheKeysProtocol(Protocol):
    """Protocol for generating cache keys.

    Abstracts cache key construction used by application layer handlers.
    Infrastructure layer provides concrete implementation.

    All keys follow hierarchical structure: {prefix}:{domain}:{resource}:{id}

    Example:
        class RefreshAccessTokenHandler:
            def __init__(
                self,
                cache_keys: CacheKeysProtocol | None = None,
                ...
            ) -> None:
                self._cache_keys = cache_keys
    """

    @property
    def prefix(self) -> str:
        """Cache key prefix (typically \"dashtam\")."""
        ...

    def user(self, user_id: UUID) -> str:
        """User data cache key.

        Pattern: {prefix}:user:{user_id}

        Args:
            user_id: User UUID.

        Returns:
            Cache key string.
        """
        ...

    def provider_connection(self, connection_id: UUID) -> str:
        """Provider connection cache key.

        Pattern: {prefix}:provider:conn:{connection_id}

        Args:
            connection_id: ProviderConnection UUID.

        Returns:
            Cache key string.
        """
        ...

    def schwab_accounts(self, user_id: UUID) -> str:
        """Schwab accounts cache key.

        Pattern: {prefix}:schwab:accounts:{user_id}

        Args:
            user_id: User UUID who owns the accounts.

        Returns:
            Cache key string.
        """
        ...

    def schwab_transactions(
        self,
        account_id: UUID,
        start_date: date,
        end_date: date,
    ) -> str:
        """Schwab transactions cache key.

        Pattern: {prefix}:schwab:tx:{account_id}:{start_date}:{end_date}

        Args:
            account_id: Account UUID.
            start_date: Transaction query start date.
            end_date: Transaction query end date.

        Returns:
            Cache key string.
        """
        ...

    def account_list(self, user_id: UUID) -> str:
        """Account list cache key.

        Pattern: {prefix}:accounts:user:{user_id}

        Args:
            user_id: User UUID who owns the accounts.

        Returns:
            Cache key string.
        """
        ...

    def security_global_version(self) -> str:
        """Security global token version cache key.

        Pattern: {prefix}:security:global_version

        Returns:
            Cache key string.

        Note:
            Used for token breach rotation (F1.3b).
        """
        ...

    def security_user_version(self, user_id: UUID) -> str:
        """Security user token version cache key.

        Pattern: {prefix}:security:user_version:{user_id}

        Args:
            user_id: User UUID.

        Returns:
            Cache key string.

        Note:
            Used for token breach rotation (F1.3b).
        """
        ...

    def namespace_from_key(self, key: str) -> str:
        """Extract cache namespace from key for metrics tracking.

        Args:
            key: Cache key string.

        Returns:
            Namespace string (e.g., \"user\", \"provider\", \"accounts\").
        """
        ...
