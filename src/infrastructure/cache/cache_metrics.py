"""Cache metrics tracking for observability.

This module provides lightweight in-memory metrics tracking for cache operations.
Metrics include hit/miss counts and hit rates for monitoring cache effectiveness.

Usage:
    from src.infrastructure.cache.cache_metrics import CacheMetrics

    metrics = CacheMetrics()
    metrics.record_hit("user")
    metrics.record_miss("user")

    stats = metrics.get_stats("user")
    print(f"Hit rate: {stats['hit_rate']:.2%}")
"""

from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass
class CacheStats:
    """Cache statistics for a specific cache namespace.

    Attributes:
        hits: Number of cache hits (value found in cache).
        misses: Number of cache misses (value not in cache).
        errors: Number of cache operation errors.
    """

    hits: int = 0
    misses: int = 0
    errors: int = 0

    @property
    def total_requests(self) -> int:
        """Total cache requests (hits + misses)."""
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests

    def to_dict(self) -> dict[str, Any]:
        """Convert stats to dictionary for JSON serialization."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "errors": self.errors,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 4),
        }


class CacheMetrics:
    """In-memory cache metrics tracker.

    Thread-safe metrics tracking for cache operations. Tracks hits, misses,
    and errors per cache namespace (e.g., "user", "provider", "accounts").

    This is a lightweight, in-memory tracker suitable for development and
    production monitoring. For production, metrics can be exported to
    observability platforms (Prometheus, Datadog, etc.).

    Example:
        metrics = CacheMetrics()

        # Record operations
        metrics.record_hit("user")
        metrics.record_miss("provider")
        metrics.record_error("accounts")

        # Get stats
        stats = metrics.get_stats("user")
        print(f"User cache hit rate: {stats['hit_rate']:.2%}")

        # Get all stats
        all_stats = metrics.get_all_stats()
    """

    def __init__(self) -> None:
        """Initialize metrics tracker with empty counters."""
        self._stats: dict[str, CacheStats] = defaultdict(CacheStats)
        self._lock = Lock()

    def record_hit(self, namespace: str) -> None:
        """Record a cache hit.

        Args:
            namespace: Cache namespace (e.g., "user", "provider").
        """
        with self._lock:
            self._stats[namespace].hits += 1

    def record_miss(self, namespace: str) -> None:
        """Record a cache miss.

        Args:
            namespace: Cache namespace (e.g., "user", "provider").
        """
        with self._lock:
            self._stats[namespace].misses += 1

    def record_error(self, namespace: str) -> None:
        """Record a cache operation error.

        Args:
            namespace: Cache namespace (e.g., "user", "provider").
        """
        with self._lock:
            self._stats[namespace].errors += 1

    def get_stats(self, namespace: str) -> dict[str, Any]:
        """Get statistics for a specific namespace.

        Args:
            namespace: Cache namespace to query.

        Returns:
            Dictionary with hits, misses, errors, total_requests, hit_rate.
        """
        with self._lock:
            stats = self._stats.get(namespace, CacheStats())
            return stats.to_dict()

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all namespaces.

        Returns:
            Dictionary mapping namespace to stats dictionary.
        """
        with self._lock:
            return {
                namespace: stats.to_dict() for namespace, stats in self._stats.items()
            }

    def reset(self, namespace: str | None = None) -> None:
        """Reset metrics.

        Args:
            namespace: Optional namespace to reset. If None, reset all.
        """
        with self._lock:
            if namespace is None:
                self._stats.clear()
            else:
                self._stats[namespace] = CacheStats()


# Global singleton instance (created lazily in container)
_metrics_instance: CacheMetrics | None = None


def get_cache_metrics() -> CacheMetrics:
    """Get global cache metrics singleton.

    Returns:
        Global CacheMetrics instance.
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = CacheMetrics()
    return _metrics_instance
