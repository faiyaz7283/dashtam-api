"""Cache metrics protocol for performance tracking.

Defines the port for cache metrics collection. Infrastructure
layer implements this protocol to provide observability.

Architecture:
    - Domain layer protocol (port)
    - Infrastructure adapter: src/infrastructure/cache/cache_metrics.py
    - Used by handlers to track cache hit/miss rates

Reference:
    - docs/architecture/hexagonal.md
    - docs/architecture/observability-architecture.md
"""

from typing import Any, Protocol


class CacheMetricsProtocol(Protocol):
    """Protocol for tracking cache performance metrics.

    Abstracts cache metrics tracking used by application layer handlers.
    Infrastructure layer provides concrete implementation.

    Thread-safe metrics tracking for cache operations. Tracks hits, misses,
    and errors per cache namespace (e.g., \"user\", \"provider\", \"accounts\").

    Example:
        class ListAccountsByUserHandler:
            def __init__(
                self,
                cache_metrics: CacheMetricsProtocol | None = None,
                ...
            ) -> None:
                self._cache_metrics = cache_metrics

            async def handle(self, query: ListAccountsByUser) -> Result[...]:
                if cached_value:
                    self._cache_metrics.record_hit(\"accounts\")
                else:
                    self._cache_metrics.record_miss(\"accounts\")
    """

    def record_hit(self, namespace: str) -> None:
        """Record a cache hit.

        Args:
            namespace: Cache namespace (e.g., \"user\", \"provider\").
        """
        ...

    def record_miss(self, namespace: str) -> None:
        """Record a cache miss.

        Args:
            namespace: Cache namespace (e.g., \"user\", \"provider\").
        """
        ...

    def record_error(self, namespace: str) -> None:
        """Record a cache operation error.

        Args:
            namespace: Cache namespace (e.g., \"user\", \"provider\").
        """
        ...

    def get_stats(self, namespace: str) -> dict[str, Any]:
        """Get statistics for a specific namespace.

        Args:
            namespace: Cache namespace to query.

        Returns:
            Dictionary with hits, misses, errors, total_requests, hit_rate.
        """
        ...

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all namespaces.

        Returns:
            Dictionary mapping namespace to stats dictionary.
        """
        ...

    def reset(self, namespace: str | None = None) -> None:
        """Reset metrics.

        Args:
            namespace: Optional namespace to reset. If None, reset all.
        """
        ...
