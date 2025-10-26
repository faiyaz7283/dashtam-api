"""Factory function for rate limiter service dependency injection.

This module provides factory functions to create and configure the rate limiter
service with all its dependencies. It implements the Dependency Inversion
Principle by creating concrete implementations and injecting them into the service.

SOLID Principles:
    - D: Dependency Inversion - creates concrete implementations and injects them
    - Allows easy swapping of implementations (algorithm, storage) by changing factory

Usage:
    ```python
    from src.rate_limiter.factory import get_rate_limiter_service

    # In FastAPI startup
    rate_limiter = await get_rate_limiter_service()
    app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
    ```
"""

from redis.asyncio import Redis

from src.rate_limiter.algorithms.token_bucket import TokenBucketAlgorithm
from src.rate_limiter.service import RateLimiterService
from src.rate_limiter.storage.redis_storage import RedisRateLimitStorage


async def get_rate_limiter_service() -> RateLimiterService:
    """Factory function to create rate limiter service with dependencies.

    This function implements the Dependency Inversion Principle:
    - High-level service (RateLimiterService) depends on abstractions
    - This factory creates concrete implementations and injects them
    - Easy to swap implementations by changing factory

    The factory creates:
    1. Redis client (async) - from environment or defaults
    2. Storage backend (RedisRateLimitStorage) - uses Redis
    3. Algorithm (TokenBucketAlgorithm) - token bucket implementation
    4. Service (RateLimiterService) - orchestrator with injected dependencies

    Returns:
        Configured RateLimiterService instance ready to use.

    Example:
        ```python
        # In main.py startup
        @app.on_event("startup")
        async def startup_rate_limiter():
            rate_limiter = await get_rate_limiter_service()
            app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
        ```

    Note:
        This function is async because Redis client creation is async.
        The Redis client is configured with:
        - decode_responses=True (for proper string handling)
        - Connection pooling enabled by default
    """
    # Create Redis client (async)
    # TODO: Get Redis config from settings (host, port, password, etc.)
    # For now, using defaults that match docker-compose.dev.yml
    redis_client = Redis(
        host="redis",  # Docker service name
        port=6379,
        db=0,
        decode_responses=True,  # Required for string operations
    )

    # Create storage backend (concrete implementation)
    storage = RedisRateLimitStorage(redis_client)

    # Create algorithm (concrete implementation)
    algorithm = TokenBucketAlgorithm()

    # Create and return service (injected dependencies)
    return RateLimiterService(algorithm=algorithm, storage=storage)
