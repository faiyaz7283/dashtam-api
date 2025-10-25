"""Token Bucket rate limiting algorithm implementation.

This module implements the Token Bucket algorithm for rate limiting. It's the
recommended algorithm for financial APIs due to:
- Allows bursts (better UX than fixed window)
- Smooth traffic (better than fixed window edge cases)
- Widely understood and battle-tested

SOLID Principles:
    - S: Single responsibility (token bucket logic only)
    - O: Open for extension (can be extended without modification)
    - L: Substitutable for any RateLimitAlgorithm
    - I: Implements minimal interface (only is_allowed method)
    - D: Depends on storage abstraction (not concrete implementation)

Algorithm Overview:
    1. Token bucket starts full (max_tokens available)
    2. Each request consumes 'cost' tokens
    3. Tokens refill at constant rate (refill_rate per minute)
    4. Bucket never exceeds max_tokens capacity
    5. Request allowed if enough tokens available

Example:
    max_tokens=20, refill_rate=5.0 (5 tokens/min = 1 token every 12 seconds)
    - Start: 20 tokens available
    - Request 1: consume 1, 19 remaining
    - Wait 12 seconds: refill 1, 20 remaining
    - Burst of 20 requests: all allowed immediately, 0 remaining
    - Request 21 immediately: rejected, retry after 12 seconds

Usage:
    ```python
    from src.rate_limiting.algorithms.token_bucket import TokenBucketAlgorithm

    algorithm = TokenBucketAlgorithm()
    allowed, retry_after = await algorithm.is_allowed(
        storage=redis_storage,
        key="ip:192.168.1.1:login",
        rule=RateLimitRule(max_tokens=20, refill_rate=5.0, ...),
        cost=1
    )
    ```
"""

import logging
from typing import TYPE_CHECKING

from src.rate_limiting.algorithms.base import RateLimitAlgorithm

if TYPE_CHECKING:
    from src.rate_limiting.config import RateLimitRule
    from src.rate_limiting.storage.base import RateLimitStorage

logger = logging.getLogger(__name__)


class TokenBucketAlgorithm(RateLimitAlgorithm):
    """Token Bucket rate limiting algorithm.

    Implements the token bucket algorithm by delegating storage operations
    to the storage backend. The algorithm itself is stateless - all state
    is maintained in the storage backend (Redis, PostgreSQL, etc.).

    SOLID: Liskov Substitution Principle
        This implementation fully complies with the RateLimitAlgorithm contract:
        - Returns tuple[bool, float] (is_allowed, retry_after)
        - Never raises exceptions (fail-open on errors)
        - Respects cost parameter (consumes cost tokens, not always 1)
        - Thread-safe (no shared mutable state)

    Fail-Open Strategy:
        If storage fails (Redis down, network error, etc.), this returns
        (True, 0.0) to allow the request. This ensures rate limiting doesn't
        become a single point of failure for the application.

    Thread Safety:
        This class is thread-safe because:
        - No shared mutable state
        - All state in storage backend (with atomic operations)
        - Can be used across multiple requests concurrently

    Examples:
        Basic usage:
        ```python
        algorithm = TokenBucketAlgorithm()
        allowed, retry_after = await algorithm.is_allowed(
            storage=redis_storage,
            key="ip:192.168.1.1:login",
            rule=login_rule,
            cost=1
        )
        if not allowed:
            raise HTTPException(
                status_code=429,
                headers={"Retry-After": str(int(retry_after))},
                detail=f"Rate limit exceeded. Try again in {int(retry_after)} seconds."
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

    async def is_allowed(
        self,
        storage: "RateLimitStorage",
        key: str,
        rule: "RateLimitRule",
        cost: int = 1,
    ) -> tuple[bool, float]:
        """Check if request is allowed under token bucket algorithm.

        Args:
            storage: Storage backend for rate limit state.
            key: Unique identifier for rate limit bucket.
            rule: Rate limit configuration (max_tokens, refill_rate, etc.).
            cost: Number of tokens to consume (default: 1).

        Returns:
            Tuple of (is_allowed, retry_after_seconds):
                - is_allowed: True if request allowed, False if rate limited.
                - retry_after_seconds: If rate limited, seconds until next token.
                  If allowed, this is 0.0.

        Raises:
            No exceptions are raised. All errors are caught and logged,
            with fail-open behavior (return True, 0.0).

        Implementation:
            1. Delegate atomic check-and-consume to storage backend
            2. Storage returns (allowed, retry_after, remaining)
            3. We return (allowed, retry_after) to caller
            4. If storage fails, log error and fail-open

        Examples:
            ```python
            allowed, retry_after = await algorithm.is_allowed(
                storage=redis_storage,
                key="ip:192.168.1.1:login",
                rule=RateLimitRule(
                    strategy=RateLimitStrategy.TOKEN_BUCKET,
                    storage=RateLimitStorage.REDIS,
                    max_tokens=20,
                    refill_rate=5.0,
                    scope="ip",
                    enabled=True
                ),
                cost=1
            )
            ```
        """
        try:
            # Delegate to storage backend (atomic operation)
            allowed, retry_after, remaining = await storage.check_and_consume(
                key=key,
                max_tokens=rule.max_tokens,
                refill_rate=rule.refill_rate,
                cost=cost,
            )

            if allowed:
                logger.debug(
                    f"Rate limit check passed for key={key}, "
                    f"remaining={remaining}/{rule.max_tokens} tokens"
                )
            else:
                logger.warning(
                    f"Rate limit exceeded for key={key}, "
                    f"retry_after={retry_after:.2f}s, "
                    f"current_tokens={remaining}, "
                    f"needed={cost}"
                )

            return allowed, retry_after

        except Exception as e:
            # Fail-open: Allow request if storage fails
            # This ensures rate limiting doesn't break the application
            logger.error(
                f"Token bucket algorithm failed for key={key}: {e}. "
                f"Failing open (allowing request)."
            )
            return True, 0.0
