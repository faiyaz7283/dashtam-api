"""Generic Rate Limiter package.

This package provides a comprehensive, SOLID-compliant Rate Limiter solution
following the Strategy Pattern and Dependency Injection principles.

**IMPORTANT**: This is a GENERIC component with NO application-specific configuration.
Applications must provide their own rate limit rules via dependency injection.

Architecture:
    - config.py: Generic models (RateLimitRule, strategies, storage enums)
    - algorithms/: Pluggable Rate Limiter algorithms (token bucket, sliding window, etc.)
    - storage/: Pluggable storage backends (Redis, PostgreSQL, memory)
    - service.py: Orchestrator service (accepts rules via DI)
    - middleware.py: FastAPI middleware integration

SOLID Compliance:
    - S: Each component has single responsibility
    - O: Open for extension (add algorithms/storage via inheritance)
    - L: All implementations substitutable (Strategy Pattern)
    - I: Minimal interfaces (no fat interfaces)
    - D: Depends on abstractions (Dependency Injection)

Quick Start:
    ```python
    from redis.asyncio import Redis
    from src.rate_limiter import (
        RateLimiterService,
        TokenBucketAlgorithm,
        RedisRateLimitStorage,
        RateLimitRule,
        RateLimitStrategy,
        RateLimitStorageEnum,
    )

    # Define application-specific rules
    rules = {
        "POST /api/v1/auth/login": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorageEnum.REDIS,
            max_tokens=20,
            refill_rate=5.0,
            scope="ip",
            enabled=True,
        ),
    }

    # Setup (typically in FastAPI startup)
    redis_client = Redis(host="localhost", port=6379, decode_responses=True)
    algorithm = TokenBucketAlgorithm()
    storage = RedisRateLimitStorage(redis_client)
    rate_limiter = RateLimiterService(algorithm, storage, rules)

    # Usage (in endpoint or middleware)
    allowed, retry_after, rule = await rate_limiter.is_allowed(
        endpoint="POST /api/v1/auth/login",
        identifier=client_ip,
        cost=1
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            headers={"Retry-After": str(int(retry_after))},
            detail="Rate limit exceeded"
        )
    ```

For more information, see:
    - docs/research/rate-limiting-research.md (algorithm comparison)
    - docs/development/implementation/rate-limiting-implementation.md (full implementation guide)
"""

# Configuration
from src.rate_limiter.config import (
    RateLimitRule,
    RateLimitStorage as RateLimitStorageEnum,
    RateLimitStrategy,
)

# Algorithms
from src.rate_limiter.algorithms import (
    RateLimitAlgorithm,
    TokenBucketAlgorithm,
)

# Storage
from src.rate_limiter.storage import (
    RateLimitStorage,
    RedisRateLimitStorage,
)

# Service
from src.rate_limiter.service import RateLimiterService

__all__ = [
    # Configuration
    "RateLimitRule",
    "RateLimitStrategy",
    "RateLimitStorageEnum",
    # Algorithms
    "RateLimitAlgorithm",
    "TokenBucketAlgorithm",
    # Storage
    "RateLimitStorage",
    "RedisRateLimitStorage",
    # Service
    "RateLimiterService",
]
