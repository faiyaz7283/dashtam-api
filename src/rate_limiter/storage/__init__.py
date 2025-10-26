"""Rate limiting storage backends package.

This package contains all rate limiting storage implementations following
the Strategy Pattern. Each storage backend implements the RateLimitStorage
interface and can be swapped without changing the algorithm or service code.

Available Storage Backends:
    - RedisRateLimitStorage: Redis with Lua scripts (production default)
    - PostgresRateLimitStorage: PostgreSQL with transactions (coming in future phase)
    - MemoryRateLimitStorage: In-memory storage (coming in future phase, testing only)

Usage:
    ```python
    from src.rate_limiter.storage import RateLimitStorage, RedisRateLimitStorage

    storage = RedisRateLimitStorage(redis_client)
    allowed, retry_after, remaining = await storage.check_and_consume(
        key, max_tokens, refill_rate, cost
    )
    ```
"""

from src.rate_limiter.storage.base import RateLimitStorage
from src.rate_limiter.storage.redis_storage import RedisRateLimitStorage

__all__ = [
    "RateLimitStorage",
    "RedisRateLimitStorage",
]
