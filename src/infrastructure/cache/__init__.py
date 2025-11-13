"""Cache infrastructure package.

This package provides Redis cache implementation.
All cache dependencies are managed through src.core.container.

Architecture:
- RedisAdapter: Concrete Redis implementation of CacheProtocol
- Use src.core.container.get_cache() for dependency injection
"""

from src.infrastructure.cache.redis_adapter import RedisAdapter

__all__ = [
    "RedisAdapter",
]
