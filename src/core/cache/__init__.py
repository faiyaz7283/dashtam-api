"""Cache abstraction for session management.

This package provides a SOLID-compliant cache interface for session token blacklist
operations. It's separate from the rate limiter's Redis to maintain clean separation
of concerns.
"""

from src.core.cache.base import CacheBackend, CacheError
from src.core.cache.redis_cache import RedisCache
from src.core.cache.factory import get_cache

__all__ = ["CacheBackend", "CacheError", "RedisCache", "get_cache"]
