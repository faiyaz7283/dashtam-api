"""Cache infrastructure package.

This package provides Redis cache implementation.
All cache dependencies are managed through src.core.container.

Architecture:
- RedisAdapter: Concrete Redis implementation of CacheProtocol
- RedisSessionCache: Session-specific cache with user indexing
- RedisProviderConnectionCache: Provider connection cache
- Use src.core.container.get_cache() for dependency injection
"""

from src.infrastructure.cache.provider_connection_cache import (
    RedisProviderConnectionCache,
)
from src.infrastructure.cache.redis_adapter import RedisAdapter
from src.infrastructure.cache.session_cache import RedisSessionCache

__all__ = [
    "RedisAdapter",
    "RedisProviderConnectionCache",
    "RedisSessionCache",
]
