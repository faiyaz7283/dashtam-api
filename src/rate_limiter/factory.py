"""Factory function for Rate Limiter service dependency injection.

This module provides factory functions to create and configure the Rate Limiter
service with all its dependencies. It implements the Dependency Inversion
Principle by creating concrete implementations and injecting them into the service.

**IMPORTANT**: This is a GENERIC factory that requires application-specific rules
to be passed as parameters. It does NOT import application configuration directly.

SOLID Principles:
    - D: Dependency Inversion - creates concrete implementations and injects them
    - Allows easy swapping of implementations (algorithm, storage, rules)
    - Generic component (no application-specific imports)

Usage:
    ```python
    from src.rate_limiter.factory import get_rate_limiter_service
    from src.config.rate_limits import RATE_LIMIT_RULES

    # In FastAPI startup
    rate_limiter = await get_rate_limiter_service(rules=RATE_LIMIT_RULES)
    app.add_middleware(RateLimitMiddleware, rate_limiter=rate_limiter)
    ```
"""

from redis.asyncio import Redis

from src.rate_limiter.algorithms.token_bucket import TokenBucketAlgorithm
from src.rate_limiter.config import RateLimitRule
from src.rate_limiter.service import RateLimiterService
from src.rate_limiter.storage.redis_storage import RedisRateLimitStorage


async def get_rate_limiter_service(
    rules: dict[str, RateLimitRule],
) -> RateLimiterService:
    """Factory function to create Rate Limiter service with dependencies.

    This function implements the Dependency Inversion Principle:
    - High-level service (RateLimiterService) depends on abstractions
    - This factory creates concrete implementations and injects them
    - Application-specific rules are injected via parameter
    - Easy to swap implementations by changing factory

    The factory creates:
    1. Redis client (async) - from environment or defaults
    2. Storage backend (RedisRateLimitStorage) - uses Redis
    3. Algorithm (TokenBucketAlgorithm) - token bucket implementation
    4. Service (RateLimiterService) - orchestrator with all dependencies injected

    Args:
        rules: Application-specific rate limit rules mapping endpoints to RateLimitRule objects.
               This MUST be provided by the calling application.

    Returns:
        Configured RateLimiterService instance ready to use.

    Example:
        ```python
        from src.config.rate_limits import RATE_LIMIT_RULES

        # In main.py startup
        @app.on_event("startup")
        async def startup_rate_limiter():
            rate_limiter = await get_rate_limiter_service(rules=RATE_LIMIT_RULES)
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

    # Create and return service with injected rules
    return RateLimiterService(algorithm=algorithm, storage=storage, rules=rules)
