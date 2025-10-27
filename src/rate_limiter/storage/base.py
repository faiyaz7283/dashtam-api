"""Abstract base class for Rate Limiter storage backends.

This module defines the interface that all Rate Limiter storage implementations
must follow. It follows the Strategy Pattern, allowing storage backends to be
swapped without changing the Rate Limiter service or algorithm code.

SOLID Principles:
    - S: Single responsibility (defines storage contract only)
    - O: Open for extension (new storage backends via inheritance)
    - L: Liskov Substitution (all implementations must be substitutable)
    - I: Interface Segregation (minimal interface, only essential methods)
    - D: Depended upon by algorithms (not vice versa)

Key Design Decisions:
    1. Atomic operations required
       - check_and_consume must be atomic (prevent race conditions)
       - Redis: Use Lua scripts
       - PostgreSQL: Use transactions
       - Memory: Use locks

    2. Fail-open strategy
       - If storage fails, return success (don't break app)
       - Log errors for monitoring
       - Rate Limiter is not single point of failure

    3. Storage doesn't know about algorithms or HTTP
       - Generic operations (check_and_consume, get_remaining, reset)
       - No dependency on algorithm details
       - No dependency on request/response objects

Usage:
    ```python
    from src.rate_limiter.storage.base import RateLimitStorage

    class MyStorage(RateLimitStorage):
        async def check_and_consume(self, key, max_tokens, refill_rate, cost):
            # Atomic implementation here
            ...
    ```
"""

from abc import ABC, abstractmethod


class RateLimitStorage(ABC):
    """Abstract base class for Rate Limiter storage backends.

    All storage implementations must inherit from this class and implement
    the three required methods. This ensures consistent behavior and allows
    storage backends to be swapped without changing algorithm or service code.

    SOLID: Liskov Substitution Principle
        Any implementation of this interface must be substitutable for any other.
        This means:
        - Same method signatures (parameters and return types)
        - Same behavioral contract (documented below)
        - Atomic operations (prevent race conditions)
        - Fail-open on errors (return success, log error)

    Contract Requirements (Liskov Substitution):
        1. check_and_consume MUST be atomic (no race conditions)
        2. MUST fail-open on errors (return success, don't break app)
        3. MUST calculate retry_after accurately
        4. MUST handle concurrent requests safely
        5. MUST log errors for monitoring

    Thread Safety:
        - All methods MUST be thread-safe
        - Atomic operations required (Lua scripts, transactions, locks)
        - No race conditions between check and consume

    Examples:
        Redis Storage (Lua script for atomicity):
        ```python
        class RedisRateLimitStorage(RateLimitStorage):
            async def check_and_consume(self, key, max_tokens, refill_rate, cost):
                # Execute Lua script atomically in Redis
                allowed, retry_after, remaining = await self._execute_lua_script(...)
                return allowed, retry_after, remaining
        ```
    """

    @abstractmethod
    async def check_and_consume(
        self,
        key: str,
        max_tokens: int,
        refill_rate: float,
        cost: int = 1,
    ) -> tuple[bool, float, int]:
        """Atomically check if tokens available and consume them if so.

        This is the core operation for token bucket Rate Limiter. It must be
        atomic to prevent race conditions where multiple requests check at the
        same time and all get allowed.

        Args:
            key: Unique identifier for rate limit bucket (e.g., "ip:127.0.0.1:login").
            max_tokens: Maximum capacity of the bucket.
            refill_rate: Tokens refilled per minute.
            cost: Number of tokens to consume (default: 1).

        Returns:
            Tuple of (is_allowed, retry_after_seconds, remaining_tokens):
                - is_allowed: True if request allowed, False if rate limited.
                - retry_after_seconds: Seconds until enough tokens available.
                  If allowed, this is 0.0.
                - remaining_tokens: Number of tokens remaining after this operation.
                  If rate limited, this is current tokens (before consuming).

        Raises:
            No exceptions should be raised. Implementation must catch all errors
            internally and fail-open (return True, 0.0, max_tokens) if storage fails.

        Implementation Notes:
            1. MUST be atomic (no race conditions)
               - Redis: Use Lua script (runs inside Redis, atomic)
               - PostgreSQL: Use transaction (BEGIN...COMMIT)
               - Memory: Use threading.Lock or asyncio.Lock

            2. Token bucket algorithm logic:
               ```python
               now = current_timestamp()
               elapsed_seconds = now - last_refill_time
               tokens_to_add = elapsed_seconds * (refill_rate / 60.0)
               current_tokens = min(last_tokens + tokens_to_add, max_tokens)

               if current_tokens >= cost:
                   # Allow request, consume tokens
                   new_tokens = current_tokens - cost
                   return (True, 0.0, new_tokens)
               else:
                   # Rate limited, calculate retry_after
                   tokens_needed = cost - current_tokens
                   retry_after = tokens_needed / (refill_rate / 60.0)
                   return (False, retry_after, current_tokens)
               ```

            3. Fail-open on errors
               - If storage unavailable: return (True, 0.0, max_tokens)
               - Log error for monitoring
               - Don't break the application

        Examples:
            Basic usage (within algorithm):
            ```python
            allowed, retry_after, remaining = await storage.check_and_consume(
                key="ip:192.168.1.1:login",
                max_tokens=20,
                refill_rate=5.0,  # 5 tokens/min
                cost=1
            )
            if not allowed:
                # Rate limited, wait retry_after seconds
                return False, retry_after
            # Allowed, remaining tokens available for next requests
            return True, 0.0
            ```

            Expensive operation (costs 5 tokens):
            ```python
            allowed, retry_after, remaining = await storage.check_and_consume(
                key="user:123:schwab_api",
                max_tokens=100,
                refill_rate=100.0,
                cost=5  # This operation costs 5 tokens
            )
            ```
        """
        ...

    @abstractmethod
    async def get_remaining(
        self,
        key: str,
        max_tokens: int,
    ) -> int:
        """Get remaining tokens for a key without consuming any.

        This is used for informational purposes (e.g., including X-RateLimit-Remaining
        header in responses). It does not consume tokens.

        Args:
            key: Unique identifier for rate limit bucket.
            max_tokens: Maximum capacity of the bucket.

        Returns:
            Number of tokens currently available. If key doesn't exist or
            storage fails, returns max_tokens (fail-open).

        Raises:
            No exceptions should be raised. Implementation must catch all errors
            internally and fail-open (return max_tokens) if storage fails.

        Examples:
            ```python
            remaining = await storage.get_remaining(
                key="ip:192.168.1.1:login",
                max_tokens=20
            )
            # Add to response headers
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            ```
        """
        ...

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset rate limit for a key (delete bucket state).

        This is used for testing and potentially for admin operations
        (e.g., manually resetting rate limits for a user).

        Args:
            key: Unique identifier for rate limit bucket.

        Raises:
            No exceptions should be raised. Implementation must catch all errors
            internally and log them. If storage fails, operation is silently ignored.

        Examples:
            ```python
            # Reset rate limit for IP (admin operation)
            await storage.reset("ip:192.168.1.1:login")

            # Reset in tests
            await storage.reset("test:user:123:api")
            ```
        """
        ...
