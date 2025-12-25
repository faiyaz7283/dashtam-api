"""Cache key construction utilities.

This module provides centralized cache key construction to ensure consistency
across all cache operations. All keys follow the pattern: {prefix}:{domain}:{resource}:{id}

Usage:
    from src.core.container import get_settings
    from src.infrastructure.cache.cache_keys import CacheKeys

    settings = get_settings()
    keys = CacheKeys(prefix=settings.cache_key_prefix)

    # Construct keys
    user_key = keys.user(user_id)
    provider_key = keys.provider_connection(connection_id)
"""

from dataclasses import dataclass
from datetime import date
from uuid import UUID


@dataclass
class CacheKeys:
    """Centralized cache key construction utilities.

    Ensures consistent key patterns across all cache operations.
    All keys follow hierarchical structure: {prefix}:{domain}:{resource}:{id}

    Attributes:
        prefix: Cache key prefix (typically "dashtam").

    Example:
        keys = CacheKeys(prefix="dashtam")
        key = keys.user(user_id)  # "dashtam:user:{user_id}"
    """

    prefix: str

    def user(self, user_id: UUID) -> str:
        """User data cache key.

        Pattern: {prefix}:user:{user_id}

        Args:
            user_id: User UUID.

        Returns:
            Cache key string.

        Example:
            "dashtam:user:123e4567-e89b-12d3-a456-426614174000"
        """
        return f"{self.prefix}:user:{user_id}"

    def provider_connection(self, connection_id: UUID) -> str:
        """Provider connection cache key.

        Pattern: {prefix}:provider:conn:{connection_id}

        Args:
            connection_id: ProviderConnection UUID.

        Returns:
            Cache key string.

        Example:
            "dashtam:provider:conn:456e7890-e89b-12d3-a456-426614174001"
        """
        return f"{self.prefix}:provider:conn:{connection_id}"

    def schwab_accounts(self, user_id: UUID) -> str:
        """Schwab accounts cache key.

        Pattern: {prefix}:schwab:accounts:{user_id}

        Args:
            user_id: User UUID who owns the accounts.

        Returns:
            Cache key string.

        Example:
            "dashtam:schwab:accounts:123e4567-e89b-12d3-a456-426614174000"
        """
        return f"{self.prefix}:schwab:accounts:{user_id}"

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

        Example:
            "dashtam:schwab:tx:789e0123-e89b-12d3-a456-426614174002:2025-01-01:2025-01-31"
        """
        return f"{self.prefix}:schwab:tx:{account_id}:{start_date}:{end_date}"

    def account_list(self, user_id: UUID) -> str:
        """Account list cache key.

        Pattern: {prefix}:accounts:user:{user_id}

        Args:
            user_id: User UUID who owns the accounts.

        Returns:
            Cache key string.

        Example:
            "dashtam:accounts:user:123e4567-e89b-12d3-a456-426614174000"
        """
        return f"{self.prefix}:accounts:user:{user_id}"

    def namespace_from_key(self, key: str) -> str:
        """Extract cache namespace from key for metrics tracking.

        Args:
            key: Cache key string.

        Returns:
            Namespace string (e.g., "user", "provider", "accounts").

        Example:
            key = "dashtam:user:123e4567-e89b-12d3-a456-426614174000"
            namespace = keys.namespace_from_key(key)  # "user"
        """
        parts = key.split(":")
        if len(parts) >= 2:
            return parts[1]
        return "unknown"
