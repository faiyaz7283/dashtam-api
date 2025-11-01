"""Rate Limiter configuration models.

This module provides generic configuration models for the rate limiter component.
It defines strategies, storage backends, and the rate limit rule structure.

This is a GENERIC component with NO application-specific configuration.
Applications using this rate limiter should define their own rules and
inject them via dependency injection.

SOLID Principles:
    - S: Single responsibility (model definitions only)
    - O: Open for extension (add new strategies/storage types via enums)
    - L: N/A (no inheritance relationships)
    - I: N/A (no interfaces)
    - D: No dependencies on application code (pure generic models)

Key Design Decisions:
    1. Generic, reusable models
       - No application-specific endpoint rules
       - Applications inject their own rules via RateLimiterService constructor
       - Type-safe with Pydantic validation

    2. Per-endpoint flexibility
       - Each endpoint can specify its own strategy (token bucket, sliding window, etc.)
       - Each endpoint can specify its own storage (Redis, PostgreSQL, memory)
       - Supports different limits for different operations

    3. Immutable rules (frozen Pydantic models)
       - Prevents accidental modification at runtime
       - Thread-safe by design

Usage:
    ```python
    from src.rate_limiter.config import RateLimitRule, RateLimitStrategy, RateLimitStorage

    # Define application-specific rules
    rules = {
        "POST /api/v1/auth/login": RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5.0,
            scope="ip",
            enabled=True,
        ),
    }

    # Inject rules into RateLimiterService
    rate_limiter = RateLimiterService(algorithm, storage, rules)
    ```
"""

from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


class RateLimitStrategy(str, Enum):
    """Rate Limiter algorithm strategies.

    Attributes:
        TOKEN_BUCKET: Allows bursts, smooth traffic. Best for financial APIs.
        SLIDING_WINDOW: Prevents timing attacks, consistent enforcement.
        FIXED_WINDOW: Simple, edge-case burst vulnerability.
    """

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


class RateLimitStorage(str, Enum):
    """Storage backend for rate limit state.

    Attributes:
        REDIS: High-performance in-memory storage (production default).
        POSTGRES: Persistent storage, good for audit requirements.
        MEMORY: Local in-process storage (testing/development only).
    """

    REDIS = "redis"
    POSTGRES = "postgres"
    MEMORY = "memory"


class RateLimitRule(BaseModel):
    """Configuration for a single rate limit rule.

    This defines how Rate Limiter is applied to a specific endpoint or operation.

    Attributes:
        strategy: Algorithm to use (token bucket, sliding window, etc.).
        storage: Storage backend for rate limit state.
        max_tokens: Maximum capacity (tokens in bucket, requests in window).
        refill_rate: Rate of token/request replenishment (per minute).
        scope: Identifier type for rate limit key (ip, user, user_provider, global).
        enabled: Whether this rule is active.
        cost: Number of tokens consumed per request (default: 1).

    Examples:
        Login endpoint (IP-based, 20 requests/min):
        ```python
        RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=20,
            refill_rate=5.0,  # 5 tokens/min = 12 seconds per token
            scope="ip",
            enabled=True
        )
        ```

        Provider API call (user-per-provider, 100 requests/min):
        ```python
        RateLimitRule(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            storage=RateLimitStorage.REDIS,
            max_tokens=100,
            refill_rate=100.0,  # Match Schwab's actual API limits
            scope="user_provider",
            enabled=True
        )
        ```
    """

    model_config = ConfigDict(frozen=True)  # Immutable for thread safety

    strategy: RateLimitStrategy = Field(
        ..., description="Rate Limiter algorithm to use"
    )
    storage: RateLimitStorage = Field(..., description="Storage backend for state")
    max_tokens: int = Field(..., gt=0, description="Maximum tokens/requests allowed")
    refill_rate: float = Field(
        ..., gt=0, description="Token/request refill rate per minute"
    )
    scope: str = Field(
        ...,
        description="Identifier type: 'ip', 'user', 'user_provider', 'global'",
    )
    enabled: bool = Field(True, description="Whether Rate Limiter is active")
    cost: int = Field(1, gt=0, description="Number of tokens consumed per request")
