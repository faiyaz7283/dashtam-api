"""Abstract base class for rate limiting algorithms.

This module defines the interface that all rate limiting algorithms must implement.
It follows the Strategy Pattern, allowing algorithms to be swapped without changing
the rate limiter service code.

SOLID Principles:
    - S: Single responsibility (defines algorithm contract only)
    - O: Open for extension (new algorithms via inheritance)
    - L: Liskov Substitution (all implementations must be substitutable)
    - I: Interface Segregation (minimal interface, only essential method)
    - D: Depended upon by service (not vice versa)

Key Design Decisions:
    1. Minimal interface (only one abstract method)
       - Keeps implementation simple
       - Easy to add new algorithms

    2. Algorithm doesn't know about HTTP/FastAPI
       - Takes generic parameters (key, tokens, rate)
       - No dependency on request/response objects
       - Pure rate limiting logic

    3. Error handling is algorithm's responsibility
       - Must never raise exceptions to caller
       - Fail-open strategy (allow request on errors)
       - Log errors for monitoring

Usage:
    ```python
    from src.rate_limiting.algorithms.base import RateLimitAlgorithm

    class MyAlgorithm(RateLimitAlgorithm):
        async def is_allowed(self, storage, key, rule, cost):
            # Implementation here
            ...
    ```
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.rate_limiting.config import RateLimitRule
    from src.rate_limiting.storage.base import RateLimitStorage


class RateLimitAlgorithm(ABC):
    """Abstract base class for rate limiting algorithms.

    All rate limiting algorithms must inherit from this class and implement
    the `is_allowed()` method. This ensures consistent behavior and allows
    algorithms to be swapped without changing the rate limiter service.

    SOLID: Liskov Substitution Principle
        Any implementation of this interface must be substitutable for any other.
        This means:
        - Same method signature (parameters and return type)
        - Same behavioral contract (documented below)
        - No exceptions raised to caller (handle internally)
        - Consistent fail-open behavior (allow request on errors)

    Contract Requirements (Liskov Substitution):
        1. MUST return tuple[bool, float] (is_allowed, retry_after_seconds)
        2. MUST NOT raise exceptions (caller expects no exceptions)
        3. MUST fail-open on errors (return True, 0.0 on storage failures)
        4. MUST respect the cost parameter (consume cost tokens, not always 1)
        5. MUST use storage operations atomically (prevent race conditions)
        6. MUST calculate retry_after accurately (client needs to know when to retry)

    Thread Safety:
        - Implementations MUST be thread-safe
        - No shared mutable state
        - All state stored in storage backend (Redis, etc.)

    Examples:
        Token Bucket Algorithm:
        ```python
        class TokenBucketAlgorithm(RateLimitAlgorithm):
            async def is_allowed(self, storage, key, rule, cost):
                try:
                    allowed, retry_after, remaining = await storage.check_and_consume(
                        key, rule.max_tokens, rule.refill_rate, cost
                    )
                    return allowed, retry_after
                except Exception as e:
                    logger.error(f"Token bucket failed: {e}")
                    return True, 0.0  # Fail-open
        ```
    """

    @abstractmethod
    async def is_allowed(
        self,
        storage: "RateLimitStorage",
        key: str,
        rule: "RateLimitRule",
        cost: int = 1,
    ) -> tuple[bool, float]:
        """Check if request is allowed under this rate limiting algorithm.

        Args:
            storage: Storage backend for rate limit state.
            key: Unique identifier for rate limit bucket (e.g., "ip:127.0.0.1:login").
            rule: Rate limit configuration (max_tokens, refill_rate, etc.).
            cost: Number of tokens to consume (default: 1). Some operations
                may cost more than 1 token (e.g., expensive API calls).

        Returns:
            Tuple of (is_allowed, retry_after_seconds):
                - is_allowed: True if request should be allowed, False if rate limited.
                - retry_after_seconds: If rate limited, seconds until next token available.
                  If allowed, this is 0.0.

        Raises:
            No exceptions should be raised. Implementation must catch all errors
            internally and fail-open (return True, 0.0) if storage fails.

        Implementation Notes:
            1. Use storage operations atomically
               - Redis Lua scripts for atomic check-and-consume
               - Database transactions for PostgreSQL
               - Locks for in-memory storage

            2. Fail-open on errors
               - If storage unavailable, return (True, 0.0)
               - Log error for monitoring
               - Don't let rate limiting break the application

            3. Calculate retry_after accurately
               - Clients need to know when to retry
               - Should be seconds until next token available
               - For token bucket: (cost - remaining) / refill_rate * 60

            4. Respect the cost parameter
               - Not all operations cost 1 token
               - Expensive operations may cost more
               - Check if enough tokens available before consuming

        Examples:
            Basic usage:
            ```python
            algorithm = TokenBucketAlgorithm()
            allowed, retry_after = await algorithm.is_allowed(
                storage=redis_storage,
                key="ip:192.168.1.1:login",
                rule=RateLimitRule(max_tokens=20, refill_rate=5.0, ...),
                cost=1
            )
            if not allowed:
                raise HTTPException(
                    status_code=429,
                    headers={"Retry-After": str(int(retry_after))},
                    detail="Rate limit exceeded"
                )
            ```

            Expensive operation (costs 5 tokens):
            ```python
            allowed, retry_after = await algorithm.is_allowed(
                storage=redis_storage,
                key="user:123:schwab_api",
                rule=schwab_rule,
                cost=5  # This operation costs 5 tokens
            )
            ```
        """
        ...
